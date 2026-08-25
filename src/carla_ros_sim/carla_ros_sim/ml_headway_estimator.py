#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import onnxruntime as ort
import numpy as np
import csv
import os
import time

class MLHeadwayEstimator(Node):
    def __init__(self):
        super().__init__('ml_headway_estimator')

        # paths configured for your workspace
        base_dir = 'data/multimodal_dataset_20260713_191320'
        model_path = os.path.join(base_dir, 'processed_fusion/mlp_mse_nodiff_fused.onnx')
        norm_path = os.path.join(base_dir, 'processed_fusion/mlp_mse_nodiff_fused_normalization.npz')

        # load normalization constants & feature order
        try:
            norm = np.load(norm_path, allow_pickle=True)
            self.feat_mean = norm['feat_mean']
            self.feat_std = norm['feat_std']
            self.y_mean = float(norm['y_mean'])
            self.y_std = float(norm['y_std'])
            self.feature_cols = list(norm['feature_cols'])
            self.get_logger().info(f"loaded features expected by model: {self.feature_cols}")
        except Exception as e:
            self.get_logger().error(f"failed to load normalization npz: {e}")
            raise

        # lag-mode models need a rolling history buffer this node doesn't build
        # fail loudly instead of silently feeding a wrong-length vector
        if any('lag' in c for c in self.feature_cols):
            raise NotImplementedError(
                "feature_cols contains lag features — this node only supports diff/no-diff mode")

        # initialize onnx runtime session (cuda, falls back to cpu)
        self.session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.get_logger().info('onnx model loaded successfully.')

        # state variables, lidar/camera updates tracked separately
        # inference only runs on a fresh pair
        self.latest_lidar_h = None
        self.latest_cam_h = None
        self.latest_gt = None
        self.lidar_updated = False
        self.cam_updated = False

        # setup csv logging, session_id from the launch file
        # from one run share a timestamp
        self.declare_parameter('session_id', '')
        session_id = self.get_parameter('session_id').value
        timestamp_str = session_id if session_id else str(int(time.time()))

        log_dir = 'data'
        os.makedirs(log_dir, exist_ok=True)
        self.csv_file = open(os.path.join(log_dir, f'ml_inference_log_{timestamp_str}.csv'), 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['timestamp', 'gt_headway_m', 'predicted_headway_m'])

        # subscribers (listening to the processed scalars, not raw sensors)
        self.create_subscription(Float32, '/carla/tesla_ego/headway', self.lidar_cb, 10)
        self.create_subscription(Float32, '/carla/tesla_ego/camera_headway', self.camera_cb, 10)
        self.create_subscription(Float32, '/carla/tesla_ego/ground_truth_headway', self.gt_cb, 10)

        # timer to run inference at a fixed 10hz rate
        self.create_timer(0.1, self.inference_loop)

    def lidar_cb(self, msg):
        self.latest_lidar_h = msg.data
        self.lidar_updated = True

    def camera_cb(self, msg):
        self.latest_cam_h = msg.data
        self.cam_updated = True

    def gt_cb(self, msg):
        self.latest_gt = msg.data

    def inference_loop(self):
        self.get_logger().info(
        f'tick | lidar={self.latest_lidar_h} cam={self.latest_cam_h} gt={self.latest_gt} '
        f'lidar_updated={self.lidar_updated} cam_updated={self.cam_updated}',
        throttle_duration_sec=1.0)
        # only run once both sensors have published a fresh reading since the last inference
        if None in (self.latest_lidar_h, self.latest_cam_h, self.latest_gt):
            return
        if not (self.lidar_updated and self.cam_updated):
            return

        # -1.0 is  for "no valid reading"
        if self.latest_lidar_h == -1.0 or self.latest_cam_h == -1.0:
            self.lidar_updated = False
            self.cam_updated = False
            self.get_logger().warn('skipping inference, (-1.0) reading from lidar or camera',
                                    throttle_duration_sec=1.0)
            return

        # build feature vector from feature_cols order
        raw_values = {
            'lidar_headway_m': self.latest_lidar_h,
            'camera_corrected': self.latest_cam_h,
            'diff': abs(self.latest_lidar_h - self.latest_cam_h),
        }
        x = np.array([[raw_values[c] for c in self.feature_cols]], dtype=np.float32)

        # standardize using z-score
        x_norm = (x - self.feat_mean) / self.feat_std

        # run inference
        pred_norm = self.session.run(None, {self.input_name: x_norm})[0]

        # reverse target normalization (z-score -> meters)
        predicted_headway = float(pred_norm[0]) * self.y_std + self.y_mean

        # log and flush to disk
        timestamp = self.get_clock().now().nanoseconds / 1e9
        self.csv_writer.writerow([timestamp, self.latest_gt, predicted_headway])
        self.csv_file.flush()

        self.get_logger().info(f"GT: {self.latest_gt:.2f}m | Pred: {predicted_headway:.2f}m",
                                throttle_duration_sec=1.0)

        # reset — require a fresh pair before the next inference
        self.lidar_updated = False
        self.cam_updated = False

    def destroy_node(self):
        self.csv_file.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = MLHeadwayEstimator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down ML Inference Node...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
