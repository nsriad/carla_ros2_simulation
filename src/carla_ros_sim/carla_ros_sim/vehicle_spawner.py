#!/usr/bin/env python3
import sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

#  carla python api path
carla_api_path = '/home/ruby/Nazmus_Shakib/Software/CARLA_0.9.16/PythonAPI/carla'
sys.path.append(carla_api_path)
import carla

# import custom modules
from .carla_env import CarlaEnvironment
from .sensors import SensorManager
from .controllers import PIDController, StopAndGoLeader

class CarlaVehicleSpawner(Node):
    def __init__(self):
        super().__init__('carla_vehicle_spawner')
        self.get_logger().info('Initializing Modular CARLA Vehicle Spawner...')

        self.gt_pub = self.create_publisher(Float32, '/carla/tesla_ego/ground_truth_headway', 10)

        # declare duration parameter — set via launch file
        self.declare_parameter('duration', 60)
        duration = self.get_parameter('duration').value

        if duration > 0:
            self.get_logger().info(f'Simulation will auto-stop in {duration}s.')
            self.shutdown_timer = self.create_timer(float(duration), self.shutdown_callback)

        # 1. environment and vehicle setup
        # use_custom_map=False to switch to Town04/default city driving
        self.env = CarlaEnvironment(use_custom_map=False) 
        try:
            self.world = self.env.connect()
            self.ego, self.leader = self.env.spawn_vehicles()
            self.get_logger().info('Environment connected and vehicles spawned.')
        except Exception as e:
            self.get_logger().error(f'Failed to connect/spawn: {e}')
            return

        # 2. senbsors
        self.sensor_manager = SensorManager(self.world, self.ego)
        self.sensor_manager.attach_all()
        self.get_logger().info('Sensors attached.')

        # 3. control logic
        self.pid = PIDController(target_gap=5.0, kp=0.3, ki=0.01, kd=0.6)
        self.leader_logic = StopAndGoLeader()
        
        # timer for stop-and-go wave (6 seconds)
        if self.env.use_custom_map:
            self.wave_timer = self.create_timer(6.0, self.toggle_leader)

        # 4. bind the main loop to CARLA's physics tick (10 Hz)
        self.world.on_tick(self.on_physics_tick)

    def toggle_leader(self):
        """triggered every 6 seconds to alternate the leader between braking and accelerating."""
        state_msg = self.leader_logic.toggle()
        self.get_logger().info(f'>>> LEADER IS NOW {state_msg} <<<')

    def on_physics_tick(self, snapshot):
        """10 times a second in sync with CARLA and the Lidar."""
        # update camera
        self.env.update_spectator()
        
        # ground truth headway
        gt_dist = self.env.get_ground_truth()
        
        # custom control in custom map
        if self.env.use_custom_map:
            # get longitudinal throttle/brake commands
            leader_cmd = self.leader_logic.get_control()
            ego_cmd = self.pid.get_control(current_gap=gt_dist, dt=0.1)
            
            # lock steering to zero
            leader_cmd.steer = 0.0
            ego_cmd.steer = 0.0
            
            # apply pedals
            self.leader.apply_control(leader_cmd)
            self.ego.apply_control(ego_cmd)

            # force the cars to stay centered in the lane
            for vehicle in [self.leader, self.ego]:
                transform = vehicle.get_transform()
                wp = self.env.world.get_map().get_waypoint(transform.location)
                
                # Snap the vehicle's Y-coordinate to the waypoint's exact Y-coordinate
                # Keep X (forward progress) and Z (height) exactly the same
                new_location = carla.Location(x=transform.location.x, 
                                              y=wp.transform.location.y, 
                                              z=transform.location.z)
                
                # lock the yaw
                new_rotation = carla.Rotation(pitch=transform.rotation.pitch, 
                                              yaw=wp.transform.rotation.yaw, 
                                              roll=transform.rotation.roll)
                
                vehicle.set_transform(carla.Transform(new_location, new_rotation))
        
        # publish ground truth
        msg = Float32()
        msg.data = gt_dist
        self.gt_pub.publish(msg)
        self.get_logger().info(f'ground truth: {gt_dist:.2f} m', throttle_duration_sec=1.0)

    def destroy_actors(self):
        self.get_logger().info('Cleaning up actors and sensors...')
        if hasattr(self, 'sensor_manager'):
            self.sensor_manager.cleanup()
        if hasattr(self, 'env'):
            self.env.cleanup()
        self.get_logger().info('Cleanup complete.')

    def shutdown_callback(self):
        """fires once when simulation duration is reached"""
        self.get_logger().info('Simulation duration reached — shutting down.')
        raise SystemExit

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
