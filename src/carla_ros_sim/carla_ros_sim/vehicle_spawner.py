#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import carla
import random

class CarlaVehicleSpawner(Node):
    def __init__(self):
        super().__init__('carla_vehicle_spawner')
        self.get_logger().info('Initializing CARLA 0.9.16 Vehicle Spawner Node...')
        
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
        self.spawn_ego_vehicle()

        # start a 20Hz timer to update the spectator
        # self.spectator_timer = self.create_timer(0.05, self.update_spectator_view)

        # sync camera perfectly to the physics engine
        self.world.on_tick(self.update_spectator_view)

    def spawn_ego_vehicle(self):
        # tesla model 3 for the ego vehicle
        vehicle_bp = self.blueprint_library.find('vehicle.tesla.model3')
        
        # 'tesla_ego' role_name tells CARLA this is the primary vehicle for ROS2
        vehicle_bp.set_attribute('role_name', 'tesla_ego')
        
        if not self.spawn_points:
            self.get_logger().error('No spawn points found!')
            return

        # picking a random spawn point from the list
        spawn_point = random.choice(self.spawn_points)
        
        # spawn the actor in the simulation
        self.ego_vehicle = self.world.spawn_actor(vehicle_bp, spawn_point)
        
        self.spawned_actors.append(self.ego_vehicle)

        # enable carla's internal autopilot
        tm_port = 8051
        
        # initialize the traffic manager on that specific port
        traffic_manager = self.client.get_trafficmanager(tm_port)

        # increase the number to drive slower
        traffic_manager.global_percentage_speed_difference(0.0)
        
        # making the autopilot behave better
        traffic_manager.set_global_distance_to_leading_vehicle(2.5)
        
        # Tell the ego vehicle to use the autopilot on YOUR custom port
        self.ego_vehicle.set_autopilot(True, tm_port)

        self.get_logger().info(f'Ego Vehicle spawned at: {spawn_point.location}')

        # trigger ros2 topics with nav sensors
        self.imu_gnss_sensors()

        # move the spectator camera to see it
        spectator = self.world.get_spectator()
        transform = self.ego_vehicle.get_transform()
        
        # place the camera 10 meters directly above the car looking straight down
        spectator_loc = carla.Location(transform.location.x, transform.location.y, transform.location.z + 10.0)
        spectator.set_transform(carla.Transform(spectator_loc, carla.Rotation(pitch=-90.0)))

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

    def update_spectator_view(self, snapshot):
        """continuously updates the CARLA server viewport to follow the ego vehicle."""
        if not hasattr(self, 'ego_vehicle') or self.ego_vehicle is None:
            return
            
        # get the spectator (the camera in the CARLA window)
        spectator = self.client.get_world().get_spectator()
        
        # get the vehicle's current position and rotation
        transform = self.ego_vehicle.get_transform()
        
        # calculate a position 6 meters behind and 3 meters above the vehicle
        behind_vector = transform.get_forward_vector() * -6.0
        up_vector = carla.Location(z=3.0)
        new_location = transform.location + behind_vector + up_vector
        
        # match the vehicle's yaw (direction), but pitch the camera down (-15 degrees) to look at the car
        new_rotation = carla.Rotation(pitch=-15.0, yaw=transform.rotation.yaw, roll=0.0)
        
        # apply the new transform
        spectator.set_transform(carla.Transform(new_location, new_rotation))

    def destroy_actors(self):
        self.get_logger().info('Cleaning up spawned actors...')
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
