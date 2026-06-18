import sys
import math
import random

# Append CARLA Python API path
carla_api_path = '/home/ruby/Nazmus_Shakib/Software/CARLA_0.9.16/PythonAPI/carla'
sys.path.append(carla_api_path)
import carla
from agents.navigation.global_route_planner import GlobalRoutePlanner

class CarlaEnvironment:
    def __init__(self, use_custom_map=False):
        self.use_custom_map = use_custom_map
        self.client = None
        self.world = None
        self.leader_vehicle = None
        self.ego_vehicle = None
        self.tm = None

    def connect(self):
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(30.0)
        self.world = self.client.get_world()
        return self.world

    def generate_shared_route(self, start_transform, total_distance=2000.0):
        """a shared waypoint route so vehicles don't separate at city intersections."""
        grp = GlobalRoutePlanner(self.world.get_map(), sampling_resolution=2.0)
        start_loc = start_transform.location
        start_wp = self.world.get_map().get_waypoint(start_loc)
        
        forward_wps = start_wp.next(total_distance)
        if not forward_wps:
            return []
            
        # Safely handle nested lists from complex map junctions
        end_loc = forward_wps[0].transform.location
        route = grp.trace_route(start_loc, end_loc)
        return [wp.transform.location for wp, _ in route]

    def spawn_vehicles(self):
        random.seed(42)
        bp_lib = self.world.get_blueprint_library()
        ego_bp = bp_lib.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name', 'tesla_ego')
        
        leader_bp = bp_lib.find('vehicle.lincoln.mkz_2020')
        leader_bp.set_attribute('role_name', 'leader')

        carla_map = self.world.get_map()

        if self.use_custom_map:
            # Custom Map: Spawn on straight road
            waypoints = carla_map.generate_waypoints(30.0)
            if not waypoints or len(waypoints) < 2:
                raise RuntimeError('Not enough waypoints on custom map!')
            waypoints_sorted = sorted(waypoints, key=lambda wp: wp.s)
            leader_wp = waypoints_sorted[-1]
            leader_spawn = leader_wp.transform
            leader_spawn.location.z += 0.5
            
            fwd = leader_wp.transform.get_forward_vector()
            follower_spawn = carla.Transform(
                carla.Location(x=leader_spawn.location.x - fwd.x * 12.0,
                               y=leader_spawn.location.y - fwd.y * 12.0,
                               z=leader_spawn.location.z),
                leader_spawn.rotation)
        else:
            # city map
            max_attempts = 50
            valid_spawn = False
            spawn_points = carla_map.get_spawn_points()
            
            for _ in range(max_attempts):
                leader_spawn = random.choice(spawn_points)
                leader_wp = carla_map.get_waypoint(leader_spawn.location)
                follower_waypoints = leader_wp.previous(12.0)
                
                if follower_waypoints and len(follower_waypoints) > 0:
                    follower_spawn = follower_waypoints[0].transform

                    follower_spawn.location.z += 0.5
                    valid_spawn = True
                    break
                    
            if not valid_spawn:
                raise RuntimeError('Could not find paired spawn point in city after 50 attempts.')

        self.leader_vehicle = self.world.spawn_actor(leader_bp, leader_spawn)
        self.ego_vehicle = self.world.spawn_actor(ego_bp, follower_spawn)
        
        # switch between custom vs default
        if self.use_custom_map:
            # override autopilot for custom pid control
            self.leader_vehicle.set_autopilot(False)
            self.ego_vehicle.set_autopilot(False)
        else:
            # autopilot mode with traffic manager for city map
            tm_port = 8051
            self.tm = self.client.get_trafficmanager(tm_port)
            # self.tm.set_synchronous_mode(True)
            self.tm.global_percentage_speed_difference(0.0)
            
            self.leader_vehicle.set_autopilot(True, tm_port)
            self.ego_vehicle.set_autopilot(True, tm_port)
            
            # apply shared route to keep vehicles together through intersections
            shared_route = self.generate_shared_route(leader_spawn, 1000.0)
            if shared_route:
                self.tm.set_path(self.leader_vehicle, shared_route)
                self.tm.set_path(self.ego_vehicle, shared_route)
            
            self.tm.auto_lane_change(self.leader_vehicle, False)
            self.tm.auto_lane_change(self.ego_vehicle, False)
            self.tm.distance_to_leading_vehicle(self.ego_vehicle, 5.0)
            self.tm.vehicle_percentage_speed_difference(self.leader_vehicle, 50.0) 
            self.tm.vehicle_percentage_speed_difference(self.ego_vehicle, 0.0)
            
        return self.ego_vehicle, self.leader_vehicle

    def get_ground_truth(self):
        if not self.ego_vehicle or not self.leader_vehicle: 
            return -1.0
        loc1 = self.ego_vehicle.get_transform().location
        loc2 = self.leader_vehicle.get_transform().location
        center_dist = math.sqrt((loc2.x - loc1.x)**2 + (loc2.y - loc1.y)**2)
        return center_dist - 4.8 

    def update_spectator(self):
        if not self.ego_vehicle or not self.ego_vehicle.is_alive: 
            return
        spectator = self.world.get_spectator()
        transform = self.ego_vehicle.get_transform()
        new_location = transform.location + (transform.get_forward_vector() * -10.0) + carla.Location(z=5.0)
        new_rotation = carla.Rotation(pitch=-15.0, yaw=transform.rotation.yaw, roll=0.0)
        spectator.set_transform(carla.Transform(new_location, new_rotation))

    def cleanup(self):
        if self.leader_vehicle and self.leader_vehicle.is_alive: 
            self.leader_vehicle.destroy()
        if self.ego_vehicle and self.ego_vehicle.is_alive: 
            self.ego_vehicle.destroy()
