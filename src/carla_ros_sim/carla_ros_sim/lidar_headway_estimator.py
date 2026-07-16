#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from datetime import datetime
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
        
        # publisher for filtered roi point cloud
        self.roi_pub = self.create_publisher(
            PointCloud2, '/carla/tesla_ego/top_lidar_roi', 10)

        # initialize to get the latest ground truth and its timestamp
        self.latest_gt = -1.0
        self.latest_gt_time = -1.0

        # setup csv file in the data folder
        # added gt_age_s column to track how stale the ground truth is
        # relative to each lidar scan (ideally < 0.1s at 10Hz sync)
        self.declare_parameter('session_id', '')
        session_id = self.get_parameter('session_id').value
        timestamp_str = session_id if session_id else datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_path = f'data/headway_csv/headway_log_{timestamp_str}.csv'
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)

        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'lidar_headway_m', 'gt_headway_m', 'gt_age_s'])

        self.get_logger().info('lidar headway estimator & logger started')

    def gt_callback(self, msg):
        # incoming ground truth — store value and wall-clock time of arrival
        # so we can detect stale GT when writing the csv
        self.latest_gt = msg.data
        self.latest_gt_time = self.get_clock().now().nanoseconds / 1e9  # was: time.time()

    def lidar_callback(self, msg):
        # use read_points_numpy for a plain (N, 3) float array 
        cloud_data = pc2.read_points_numpy(msg, field_names=("x", "y", "z"), skip_nans=True)

        self.get_logger().info(
            f'Fields: {[f.name for f in msg.fields]} | '
            f'Total points: {msg.width * msg.height}',
            throttle_duration_sec=2.0
        )
        self.get_logger().info(f'Points after read: {len(cloud_data)}', throttle_duration_sec=2.0)

        if len(cloud_data) > 0:
            self.get_logger().info(
                f'X: {cloud_data[:,0].min():.2f} to {cloud_data[:,0].max():.2f} | '
                f'Y: {cloud_data[:,1].min():.2f} to {cloud_data[:,1].max():.2f} | '
                f'Z: {cloud_data[:,2].min():.2f} to {cloud_data[:,2].max():.2f}',
                throttle_duration_sec=2.0
            )

        # exit if cloud is empty
        if len(cloud_data) == 0:
            return

        points_x = cloud_data[:, 0]
        points_y = cloud_data[:, 1]
        points_z = cloud_data[:, 2]

        # define region of interest (roi)
        min_x, max_x = 3.5, 80.0    # forward range in front of ego bumper
        min_y, max_y = -1.5, 1.5    # widened lateral window
        min_z, max_z = -2.0, 1.0    # vertical range covering full vehicle height

        # DIAGNOSTIC: log near-range point stats to determine the true
        # self-occlusion boundary for this sensor's mount point, before
        # committing to a final min_x value. Remove once min_x is confirmed.
        near_mask = points_x < 3.5
        if near_mask.sum() > 0:
            self.get_logger().info(
                f'[ROI DIAG] points with x<3.5: {near_mask.sum()} | '
                f'x range: {points_x[near_mask].min():.2f} to {points_x[near_mask].max():.2f} | '
                f'z range: {points_z[near_mask].min():.2f} to {points_z[near_mask].max():.2f}',
                throttle_duration_sec=2.0
            )

        # apply bounding box filter using plain array column indices
        mask = (
            (points_x > min_x) & (points_x < max_x) &
            (points_y > min_y) & (points_y < max_y) &
            (points_z > min_z) & (points_z < max_z)
        )

        roi_points_x = points_x[mask]
        roi_points_y = points_y[mask]

        # publish roi point cloud for bag recording and visualization
        if len(roi_points_x) > 0:
            roi_points = cloud_data[mask]
            roi_msg = pc2.create_cloud_xyz32(msg.header, roi_points.tolist())
            self.roi_pub.publish(roi_msg)

        if len(roi_points_x) == 0:
            headway = -1.0
        else:
            distances = np.sqrt(roi_points_x**2 + roi_points_y**2)
            headway = float(np.min(distances)) - 2.35

        # publish the calculated headway
        headway_msg = Float32()
        headway_msg.data = headway
        self.headway_pub.publish(headway_msg)

        # calculate how old the latest ground truth is relative to this lidar scan
        # values consistently above 0.05s indicate the two topics are drifting apart
        current_time = self.get_clock().now().nanoseconds / 1e9  # was: time.time()
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

