#!/usr/bin/env python3
import sys
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import carla
import random

carla_api_path = '/home/ruby/Nazmus_Shakib/Software/CARLA_0.9.16/PythonAPI/carla'
sys.path.append(carla_api_path)

from agents.navigation.global_route_planner import GlobalRoutePlanner


class CarlaVehicleSpawner(Node):
    def __init__(self):
        super().__init__('carla_vehicle_spawner')
        self.get_logger().info('Initializing CARLA 0.9.16 Vehicle Spawner Node...')

        # publisher for ground truth headway — created here, not lazily inside timer
        self.gt_pub = self.create_publisher(Float32, '/carla/tesla_ego/ground_truth_headway', 10)

        # connecting to carla server
        try:
            self.client = carla.Client('localhost', 2000)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            self.get_logger().info('Successfully connected to CARLA Server.')
        except Exception as e:
            self.get_logger().error(f'Failed to connect to CARLA: {e}')
            return

        self.blueprint_library = self.world.get_blueprint_library()
        self.spawn_points = self.world.get_map().get_spawn_points()
        self.spawned_actors = []

        # spawn ego vehicle
        self.spawn_vehicle()

        # sync camera to the physics engine
        self.world.on_tick(self.update_spectator_view)

        # timer to calculate and log ground truth distance at 10Hz
        self.gt_timer = self.create_timer(0.1, self.log_ground_truth)

    def generate_shared_route(self, start_transform, total_distance=2000.0):
        """
        Builds a waypoint route starting from start_transform, following
        the road forward for total_distance meters. Both vehicles get the
        exact same list of waypoints so they never diverge at junctions.
        """
        grp = GlobalRoutePlanner(self.world.get_map(), sampling_resolution=2.0)
        
        start_loc = start_transform.location
        
        # project forward along the road to get a far destination
        start_wp = self.world.get_map().get_waypoint(start_loc)
        
        # walk forward to find a destination point far enough ahead
        forward_wps = start_wp.next(total_distance)
        if not forward_wps:
            self.get_logger().warn('Could not find destination waypoint, using fallback.')
            return []
        
        end_loc = forward_wps[0].transform.location
        
        # trace the full route between start and end
        route = grp.trace_route(start_loc, end_loc)
        
        # extract just the waypoint transforms (not the road option enum)
        waypoints = [wp.transform.location for wp, _ in route]
        return waypoints

    def spawn_vehicle(self):
        # blueprint for follower (ego) vehicle
        ego_bp = self.blueprint_library.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'tesla_ego')

        # blueprint for leader vehicle
        leader_bp = self.blueprint_library.find('vehicle.lincoln.mkz_2020')
        leader_bp.set_attribute('role_name', 'leader')

        if not self.spawn_points:
            self.get_logger().error('No spawn points found!')
            return

        carla_map = self.world.get_map()

        max_attempts = 50
        attempts = 0
        valid_spawn = False

        while not valid_spawn and attempts < max_attempts:
            attempts += 1
            leader_spawn = random.choice(self.spawn_points)
            leader_wp = carla_map.get_waypoint(leader_spawn.location)
            follower_waypoints = leader_wp.previous(12.0)

            if len(follower_waypoints) > 0:
                valid_spawn = True
                follower_spawn = follower_waypoints[0].transform
                follower_spawn.location.z += 0.5

        if not valid_spawn:
            self.get_logger().error('Could not find valid paired spawn after 50 attempts.')
            return

        self.leader_vehicle = self.world.spawn_actor(leader_bp, leader_spawn)
        self.spawned_actors.append(self.leader_vehicle)  # spawn leader

        # spawn follower
        self.ego_vehicle = self.world.spawn_actor(ego_bp, follower_spawn)
        self.spawned_actors.append(self.ego_vehicle)

        # use default TM port 8000 to avoid colliding with leftover TM instances
        # from previous runs that didn't clean up properly
        tm_port = 8051
        self.traffic_manager = self.client.get_trafficmanager(tm_port)

        # set baseline driving behavior
        self.traffic_manager.global_percentage_speed_difference(0.0)

        # enable default autopilot for both vehicles
        self.leader_vehicle.set_autopilot(True, tm_port)
        self.ego_vehicle.set_autopilot(True, tm_port)

        # generate one shared route from the leader's spawn point
        shared_route = self.generate_shared_route(leader_spawn, 1000)

        if shared_route:
            # assign the identical route to both vehicles
            # TM will now follow these waypoints through every intersection
            self.traffic_manager.set_path(self.leader_vehicle, shared_route)
            self.traffic_manager.set_path(self.ego_vehicle, shared_route)
            self.get_logger().info(f'Shared route assigned: {len(shared_route)} waypoints.')
        else:
            self.get_logger().warn('Route generation failed!')

        # disable lane changes for both vehicles so they never diverge onto separate paths
        self.traffic_manager.auto_lane_change(self.leader_vehicle, False)
        self.traffic_manager.auto_lane_change(self.ego_vehicle, False)

        # tell the TM to maintain a 5m bumper-to-bumper gap for the ego vehicle
        self.traffic_manager.distance_to_leading_vehicle(self.ego_vehicle, 5.0)

        # keep both vehicles at a consistent speed so the follower can track reliably
        self.traffic_manager.vehicle_percentage_speed_difference(self.leader_vehicle, 0.0)
        self.traffic_manager.vehicle_percentage_speed_difference(self.ego_vehicle, 5.0)

        self.get_logger().info('Leader and follower spawned in same lane.')
        self.get_logger().info('Lane changes disabled')
        self.get_logger().info('Ego following distance set to 5.0m via Traffic Manager.')

        # trigger ros2 topics with imu and gnss sensors
        self.imu_gnss_sensors()

        # trigger ros2 topics with camera and lidar sensors
        self.camera_lidar_sensors()

    def log_ground_truth(self):
        # ensure both vehicles exist before calculating
        if not hasattr(self, 'ego_vehicle') or not hasattr(self, 'leader_vehicle'):
            return

        loc1 = self.ego_vehicle.get_transform().location
        loc2 = self.leader_vehicle.get_transform().location

        # calculate euclidean distance between centers
        center_dist = math.sqrt((loc2.x - loc1.x)**2 + (loc2.y - loc1.y)**2)

        # subtract 4.8m to get bumper-to-bumper distance
        bumper_dist = center_dist - 4.8  # half tesla + half lincoln = 2.35 + 2.45 = 4.8m

        # publish ground truth for the perception node
        msg = Float32()
        msg.data = bumper_dist
        self.gt_pub.publish(msg)

        # print to console only once per second
        self.get_logger().info(f'ground truth: {bumper_dist:.2f} m', throttle_duration_sec=1.0)

    def imu_gnss_sensors(self):
        # imu sensor for acceleration and velocity
        imu_bp = self.blueprint_library.find('sensor.other.imu')
        imu_bp.set_attribute('role_name', 'imu_sensor')
        imu = self.world.spawn_actor(imu_bp, carla.Transform(), attach_to=self.ego_vehicle)
        self.spawned_actors.append(imu)

        # gnss sensor for global position
        gnss_bp = self.blueprint_library.find('sensor.other.gnss')
        gnss_bp.set_attribute('role_name', 'gnss_sensor')
        gnss = self.world.spawn_actor(gnss_bp, carla.Transform(), attach_to=self.ego_vehicle)
        self.spawned_actors.append(gnss)

        self.get_logger().info('IMU and GNSS attached.')

    def camera_lidar_sensors(self):
        # camera & LiDAR blueprints
        camera_bp = self.blueprint_library.find('sensor.camera.rgb')
        lidar_bp = self.blueprint_library.find('sensor.lidar.ray_cast')

        # configure attributes for both sensors
        camera_bp.set_attribute('role_name', 'front_camera')
        camera_bp.set_attribute('sensor_tick', '0.1')
        camera_bp.set_attribute('image_size_x', '800')
        camera_bp.set_attribute('image_size_y', '600')
        camera_bp.set_attribute('fov', '90.0')

        lidar_bp.set_attribute('role_name', 'top_lidar')
        lidar_bp.set_attribute('sensor_tick', '0.1')
        lidar_bp.set_attribute('channels', '32')
        lidar_bp.set_attribute('points_per_second', '100000')
        lidar_bp.set_attribute('rotation_frequency', '10.0')

        # position the camera and LiDAR relative to the vehicle's center
        camera_transform = carla.Transform(carla.Location(x=1.5, z=1.2))
        lidar_transform = carla.Transform(carla.Location(x=0.0, z=1.5))

        # spawn the sensors and attach them to the ego vehicle
        self.camera = self.world.spawn_actor(camera_bp, camera_transform, attach_to=self.ego_vehicle)
        self.lidar = self.world.spawn_actor(lidar_bp, lidar_transform, attach_to=self.ego_vehicle)

        # add the sensors to the list of spawned actors for cleanup later
        self.spawned_actors.append(self.camera)
        self.spawned_actors.append(self.lidar)

        self.get_logger().info('Camera and 32-Channel LiDAR attached.')

    def update_spectator_view(self, snapshot):
        """continuously updates the CARLA server viewport to follow the ego vehicle."""
        if not hasattr(self, 'ego_vehicle') or self.ego_vehicle is None:
            return

        # verify ego is alive before updating camera
        if not self.ego_vehicle.is_alive:
            return

        # get the spectator (the camera in the CARLA window)
        spectator = self.client.get_world().get_spectator()

        # get the vehicle's current position and rotation
        transform = self.ego_vehicle.get_transform()

        # calculate a position 10 meters behind and 5 meters above the vehicle
        behind_vector = transform.get_forward_vector() * -10.0
        up_vector = carla.Location(z=5.0)
        new_location = transform.location + behind_vector + up_vector

        # match the vehicle's yaw (direction), but pitch the camera down (-15 degrees) to look at the car
        new_rotation = carla.Rotation(pitch=-15.0, yaw=transform.rotation.yaw, roll=0.0)

        # apply the new transform
        spectator.set_transform(carla.Transform(new_location, new_rotation))

    def destroy_actors(self):
        self.get_logger().info('Cleaning up spawned actors...')

        # stop sensor callbacks before destroying to avoid callbacks firing on dead actors
        if hasattr(self, 'camera') and self.camera.is_alive:
            self.camera.stop()
        if hasattr(self, 'lidar') and self.lidar.is_alive:
            self.lidar.stop()

        for actor in self.spawned_actors:
            if actor.is_alive:
                actor.destroy()
        self.get_logger().info('Cleanup complete.')

def main(args=None):
    rclpy.init(args=args)
    node = CarlaVehicleSpawner()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down node...')
    finally:
        node.destroy_actors()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
