#!/usr/bin/env python3
"""
USAGE:
    python3 fusion/least_squares_fusion.py \\
        --merged_csv ../data/multimodal_dataset_20260713_191320/merged_cam_lid_gt.csv \\
        --train_frac 0.5
"""

import argparse
import os
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--merged_csv", required=True,
                   help="merged_cam_lid_gt.csv from headway_analysis.py")
    p.add_argument("--train_frac", type=float, default=0.5,
                   help="Fraction of the drive (by time, not shuffled) used to fit theta")
    p.add_argument("--output_dir", default=None, help="Default: <dataset>/processed_fusion")
    return p.parse_args()


def mae_rmse(pred, gt):
    err = pred - gt
    return np.mean(np.abs(err)), np.sqrt(np.mean(err ** 2))


def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.merged_csv), 'processed_fusion')
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(args.merged_csv).sort_values("time").reset_index(drop=True)
    print(f"loaded {len(df)} time-aligned frames\n")

    n_train = int(args.train_frac * len(df))
    train = df.iloc[:n_train]
    test = df.iloc[n_train:]
    print(f"train = first {len(train)} frames, test = last {len(test)} frames\n")

    # fit theta via least squares on train only
    # f_theta(lidar, cam) = theta0 + theta1*lidar + theta2*cam
    A_train = np.vstack([
        np.ones(len(train)),
        train["lidar_headway_m"].values,
        train["camera_corrected"].values,
    ]).T
    y_train = train["gt_headway_m"].values

    theta, _, _, _ = np.linalg.lstsq(A_train, y_train, rcond=None)
    theta0, theta1, theta2 = theta
    print(f"fitted f_theta: fused = {theta0:.4f} + {theta1:.4f}*lidar + {theta2:.4f}*camera")
    print(f"(theta1 is lidar's learned weight, theta2 is camera's, bigger magnitude means more trusted)\n")

    # apply to test, never used for fitting
    fused_test = theta0 + theta1 * test["lidar_headway_m"].values + theta2 * test["camera_corrected"].values
    gt_test = test["gt_headway_m"].values

    mae_lidar, rmse_lidar = mae_rmse(test["lidar_headway_m"].values, gt_test)
    mae_cam, rmse_cam = mae_rmse(test["camera_corrected"].values, gt_test)
    mae_fused, rmse_fused = mae_rmse(fused_test, gt_test)

    results = pd.DataFrame([
        {"sensor": "LiDAR alone", "MAE": mae_lidar, "RMSE": rmse_lidar},
        {"sensor": "Camera alone (calibrated)", "MAE": mae_cam, "RMSE": rmse_cam},
        {"sensor": "Least-squares fusion", "MAE": mae_fused, "RMSE": rmse_fused},
    ])

    print("=" * 55)
    print("results on test frames")
    print("=" * 55)
    print(results.to_string(index=False))

    # save one report with everything needed to reproduce this run
    with open(os.path.join(output_dir, "least_squares_report.txt"), "w") as f:
        f.write(f"f_theta(lidar, cam) = {theta0:.4f} + {theta1:.4f}*lidar + {theta2:.4f}*cam\n")
        f.write(f"train: first {len(train)} frames | test: last {len(test)} frames\n\n")
        f.write(results.to_string(index=False))

    # write into the shared comparison file, aligned by time and assigned
    # directly, no merge, so reruns overwrite this column cleanly instead
    # of producing _x/_y duplicates
    col_name = "least_squares_fused"
    shared_path = os.path.join(output_dir, "fusion_comparison.csv")
    if os.path.exists(shared_path):
        shared = pd.read_csv(shared_path)
    else:
        shared = test[["time", "lidar_headway_m", "camera_corrected", "gt_headway_m"]].copy()

    pred_series = pd.Series(fused_test, index=test["time"].values)
    shared = shared.set_index("time")
    shared[col_name] = pred_series
    shared = shared.reset_index()

    shared.to_csv(shared_path, index=False)
    print(f"\nadded '{col_name}' column to {shared_path}")


if __name__ == "__main__":
    main()
