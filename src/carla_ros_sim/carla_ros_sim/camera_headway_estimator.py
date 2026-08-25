#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from datetime import datetime
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
import cv_bridge
import cv2
import torch
from ultralytics import YOLO
import csv
import os
import time

# coco vehicle class ids — same set as yolo_detection.py
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

class CameraHeadwayEstimator(Node):
    def __init__(self):
        super().__init__('camera_headway_estimator')

        self.cv_bridge = cv_bridge.CvBridge()

        # detection/masking params — same values yolo_detection.py used
        self.conf_thresh = 0.30
        self.exclude_bottom_px = 40

        # affine calibration fit offline in camera_calibrate.py: d_gt = a * d_cam + b
        self.calib_a = 7.2589
        self.calib_b = -11.0107

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.get_logger().info(f'loading yolov8 on {device}...')
        self.yolo_model = YOLO("yolov8n.pt").to(device)

        self.get_logger().info(f'loading zoedepth on {device}...')
        self.zoe_model = torch.hub.load(
            "isl-org/ZoeDepth", "ZoeD_K", pretrained=True, trust_repo=True).to(device).eval()
        self.get_logger().info('models loaded.')

        # subscribe to ego front camera 
        self.image_sub = self.create_subscription(
            Image, '/carla/tesla_ego/front_camera/image', self.image_callback, 10)

        # subscribe to ground truth headway from spawner
        self.gt_sub = self.create_subscription(
            Float32, '/carla/tesla_ego/ground_truth_headway', self.gt_callback, 10)

        # publisher for camera-based headway ml_headway_estimator.py subscribes to
        self.headway_pub = self.create_publisher(
            Float32, '/carla/tesla_ego/camera_headway', 10)

        self.latest_gt = -1.0
        self.latest_gt_time = -1.0

        # setup csv file in the data folder
        self.declare_parameter('session_id', '')
        session_id = self.get_parameter('session_id').value
        timestamp_str = session_id if session_id else datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_path = f'data/headway_csv/camera_headway_log_{timestamp_str}.csv'
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)

        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'camera_headway_m', 'gt_headway_m', 'gt_age_s'])

        self.get_logger().info('camera headway estimator & logger started')

    def gt_callback(self, msg):
        self.latest_gt = msg.data
        self.latest_gt_time = self.get_clock().now().nanoseconds / 1e9

    def image_callback(self, msg):

        now = time.time()
        if hasattr(self, '_last_cb_time'):
            self.get_logger().info(f'inter-callback gap: {now - self._last_cb_time:.3f}s', throttle_duration_sec=1.0)
        self._last_cb_time = now
        cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        # self.get_logger().info(f'live frame shape: {cv_image.shape}', throttle_duration_sec=5.0)
        headway = self.estimate_camera_headway(cv_image)

        headway_msg = Float32()
        headway_msg.data = headway
        self.headway_pub.publish(headway_msg)

        current_time = self.get_clock().now().nanoseconds / 1e9
        gt_age = current_time - self.latest_gt_time if self.latest_gt_time > 0 else -1.0

        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([current_time, headway, self.latest_gt, gt_age])

        if headway > 0:
            self.get_logger().info(
                f'camera: {headway:.2f}m | gt: {self.latest_gt:.2f}m | gt_age: {gt_age*1000:.1f}ms',
                throttle_duration_sec=1.0
            )
        else:
            self.get_logger().warn('no leader vehicle detected this frame', throttle_duration_sec=1.0)

    def estimate_camera_headway(self, cv_image):
        t_wall_start = time.time()
        t_sim_start = self.get_clock().now().nanoseconds / 1e9

        # mask ego hood/bumper before detection, same as yolo_detection.py
        img_infer = cv_image.copy()
        if self.exclude_bottom_px > 0:
            img_infer[-self.exclude_bottom_px:, :] = 0
        t_mask = time.time()

        results = self.yolo_model(img_infer, conf=self.conf_thresh, agnostic_nms=True, verbose=False)[0]
        t_yolo = time.time()

        # collect vehicle detections in this frame, same class filter as yolo_detection.py
        candidates = []
        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            if cls_id not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            candidates.append(((x1 + x2) // 2, y2))  # bbox_bottom_center_x, bbox_bottom_center_y

        # missing_leader_frame.py's case, no vehicle in frame at all
        if not candidates:
            return -1.0

        # find_multi_car_frame.py's case, take the one whose bbox bottom sits lowest
        bx, by = max(candidates, key=lambda c: c[1])

        # depth on the full frame, then sample the leader's pixel
        img_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        t_cvt = time.time()
        
        with torch.no_grad():
            depth_map = self.zoe_model.infer_pil(img_rgb)
            t_zoe = time.time()

        y = min(by, depth_map.shape[0] - 1)
        x = min(bx, depth_map.shape[1] - 1)
        raw_headway = float(depth_map[y, x])

        t_wall_end = time.time()
        t_sim_end = self.get_clock().now().nanoseconds / 1e9

        # self.get_logger().info(
        #     f'wall: {t_wall_end-t_wall_start:.3f}s  sim: {t_sim_end-t_sim_start:.3f}s  '
        #     f'ratio: {(t_sim_end-t_sim_start)/(t_wall_end-t_wall_start):.2f}',
        #     throttle_duration_sec=1.0)

        return self.calib_a * raw_headway + self.calib_b

def main(args=None):
    rclpy.init(args=args)
    node = CameraHeadwayEstimator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('shutting down camera headway estimator...')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
