#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import random

# active fault settings — edit these, rebuild, rerun for each scenario
DROPOUT_PROB_LIDAR = 0.4
DROPOUT_PROB_CAMERA = 0.0

class FaultInjector(Node):
    def __init__(self):
        super().__init__('fault_injector')
        random.seed(42)  # same seed each run, so results are comparable across scenarios

        self.lidar_pub = self.create_publisher(Float32, '/carla/tesla_ego/lidar_headway_faulty', 10)
        self.camera_pub = self.create_publisher(Float32, '/carla/tesla_ego/camera_headway_faulty', 10)

        self.create_subscription(Float32, '/carla/tesla_ego/lidar_headway', self.lidar_cb, 10)
        self.create_subscription(Float32, '/carla/tesla_ego/camera_headway', self.camera_cb, 10)

        self.get_logger().info(
            f'fault injector started, dropout_lidar={DROPOUT_PROB_LIDAR}, dropout_camera={DROPOUT_PROB_CAMERA}')

    def lidar_cb(self, msg):
        out = Float32()
        # only drop an already-valid reading, a reading that's already missing stays missing
        if msg.data >= 0 and random.random() < DROPOUT_PROB_LIDAR:
            out.data = -1.0
        else:
            out.data = msg.data
        self.lidar_pub.publish(out)

    def camera_cb(self, msg):
        out = Float32()
        if msg.data >= 0 and random.random() < DROPOUT_PROB_CAMERA:
            out.data = -1.0
        else:
            out.data = msg.data
        self.camera_pub.publish(out)

def main(args=None):
    rclpy.init(args=args)
    node = FaultInjector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('shutting down fault injector...')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
