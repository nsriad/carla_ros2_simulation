#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2
from std_msgs.msg import Float32
import numpy as np
import csv
import os
import time

class LidarHeadwayEstimator(Node):
    def __init__(self):
        super().__init__('lidar_headway_estimator')

        # subscribe to ego lidar
        self.lidar_sub = self.create_subscription(
            PointCloud2, '/carla/tesla_ego/top_lidar', self.lidar_callback, 10)

        # subscribe to space headway ground truth from spawner
        self.gt_sub = self.create_subscription(
            Float32, '/carla/tesla_ego/ground_truth_headway', self.gt_callback, 10)

        # publisher for headway distance
        self.headway_pub = self.create_publisher(
            Float32, '/carla/tesla_ego/headway', 10)

        # initialize to get the latest ground truth and its timestamp
        self.latest_gt = -1.0
        self.latest_gt_time = -1.0

        # setup csv file in the data folder
        # added gt_age_s column to track how stale the ground truth is
        # relative to each lidar scan (ideally < 0.1s at 10Hz sync)
        self.csv_path = 'data/headway_log.csv'
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)

        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'lidar_headway_m', 'gt_headway_m', 'gt_age_s'])

        self.get_logger().info('lidar headway estimator & logger started')

    def gt_callback(self, msg):
        # incoming ground truth — store value and wall-clock time of arrival
        # so we can detect stale GT when writing the csv
        self.latest_gt = msg.data
        self.latest_gt_time = time.time()

    def lidar_callback(self, msg):
        # use read_points_numpy for a plain (N, 3) float array — faster than
        # list(read_points()) and avoids structured-array indexing inconsistencies
        # across different ROS2 / sensor_msgs_py versions
        cloud_data = pc2.read_points_numpy(msg, field_names=("x", "y", "z"), skip_nans=True)

        # exit if cloud is empty
        if len(cloud_data) == 0:
            return

        points_x = cloud_data[:, 0]
        points_y = cloud_data[:, 1]
        points_z = cloud_data[:, 2]

        # define region of interest (roi)
        min_x, max_x = 2.0, 50.0    # forward range in front of ego bumper
        min_y, max_y = -3.0, 3.0    # widened lateral window
        min_z, max_z = -1.0, 3.0    # vertical range covering full vehicle height

        # apply bounding box filter using plain array column indices
        mask = (
            (points_x > min_x) & (points_x < max_x) &
            (points_y > min_y) & (points_y < max_y) &
            (points_z > min_z) & (points_z < max_z)
        )

        roi_points_x = points_x[mask]

        # calculate headway
        if len(roi_points_x) == 0:
            headway = -1.0  # clear road
        else:
            # subtract 2.35m for ego front bumper offset
            headway = float(np.min(roi_points_x)) - 2.35

        # publish the calculated headway
        headway_msg = Float32()
        headway_msg.data = headway
        self.headway_pub.publish(headway_msg)

        # calculate how old the latest ground truth is relative to this lidar scan
        # values consistently above 0.05s indicate the two topics are drifting apart
        current_time = time.time()
        gt_age = current_time - self.latest_gt_time if self.latest_gt_time > 0 else -1.0

        # write synced data to csv
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([current_time, headway, self.latest_gt, gt_age])

        # print to console only once per second to prevent spam
        if headway > 0:
            self.get_logger().info(
                f'lidar: {headway:.2f}m | gt: {self.latest_gt:.2f}m | gt_age: {gt_age*1000:.1f}ms',
                throttle_duration_sec=1.0
            )

def main(args=None):
    rclpy.init(args=args)
    node = LidarHeadwayEstimator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('shutting down headway estimator...')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

