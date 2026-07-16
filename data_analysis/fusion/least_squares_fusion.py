#!/usr/bin/env python3
"""
Learned linear fusion of camera + LiDAR headway estimates.

f_theta(lidar, cam) = theta0 + theta1*lidar + theta2*cam

Fit by ordinary least squares against ground truth, on a time-block split
(train on the first part of the drive, test on the later part) rather than
a random shuffle, since consecutive frames are temporally correlated.

USAGE:
    python3 fusion/least_squares_fusion.py \
        --merged_csv ../data/multimodal_dataset_20260713_191320/merged_cam_lid_gt.csv \
        --train_frac 0.5
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# global LaTeX config
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 14,
    "font.size": 12,
    "legend.fontsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--merged_csv", required=True,
                   help="merged_cam_lid_gt.csv / sensor_fusion_input.csv from headway_analysis.py")
    p.add_argument("--train_frac", type=float, default=0.5,
                   help="Fraction of the drive (by time, not shuffled) used to fit theta")
    p.add_argument("--output_dir", default=None, help="Default: same folder as merged_csv")
    return p.parse_args()


def mae_rmse(pred, gt):
    err = pred - gt
    return np.mean(np.abs(err)), np.sqrt(np.mean(err ** 2))


def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.merged_csv), 'processed_fusion')
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(args.merged_csv).sort_values("time").reset_index(drop=True)
    print(f"Loaded {len(df)} time-aligned frames.")
    print(f"Columns: {list(df.columns)}\n")

    n = len(df)
    n_train = int(args.train_frac * n)
    train = df.iloc[:n_train]
    test = df.iloc[n_train:]
    print(f"Time-block split: train = first {len(train)} frames (t={train['time'].min():.1f}-{train['time'].max():.1f}s), "
          f"test = last {len(test)} frames (t={test['time'].min():.1f}-{test['time'].max():.1f}s)\n")

    # ---- fit theta via least squares on TRAIN only ----
    # f_theta(lidar, cam) = theta0 + theta1*lidar + theta2*cam
    A_train = np.vstack([
        np.ones(len(train)),
        train["lidar_headway_m"].values,
        train["camera_corrected"].values,
    ]).T
    y_train = train["gt_headway_m"].values

    theta, _, _, _ = np.linalg.lstsq(A_train, y_train, rcond=None)
    theta0, theta1, theta2 = theta
    print(f"Fitted f_theta:")
    print(f"  fused = {theta0:.4f} + {theta1:.4f}*lidar + {theta2:.4f}*camera\n")
    print(f"  (theta1={theta1:.4f} is LiDAR's learned weight, theta2={theta2:.4f} is camera's — "
          f"larger magnitude = more trusted by the fit)\n")

    # ---- apply to TEST (never used for fitting) ----
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

    print("=" * 60)
    print("RESULTS ON HELD-OUT TEST BLOCK (never used to fit theta)")
    print("=" * 60)
    print(results.to_string(index=False))
    print()

    # ---- save ----
    results.to_csv(os.path.join(output_dir, "least_squares_results.csv"), index=False)

    test_out = test[["time", "lidar_headway_m", "camera_corrected", "gt_headway_m"]].copy()
    test_out["least_squares_fused"] = fused_test
    test_out.to_csv(os.path.join(output_dir, "least_squares_test_frames.csv"), index=False)

    with open(os.path.join(output_dir, "least_squares_report.txt"), "w") as f:
        f.write(f"f_theta(lidar, cam) = {theta0:.4f} + {theta1:.4f}*lidar + {theta2:.4f}*cam\n")
        f.write(f"Train: first {len(train)} frames | Test: last {len(test)} frames\n\n")
        f.write(results.to_string(index=False))

    # write into the shared comparison file, same convention as train_mlp_fusion.py
    shared_path = os.path.join(output_dir, "fusion_comparison.csv")
    if os.path.exists(shared_path):
        shared = pd.read_csv(shared_path)
        new_col = pd.DataFrame({"time": test["time"].values, "least_squares_fused": fused_test})
        shared = shared.merge(new_col, on="time", how="outer")
    else:
        shared = test[["time", "lidar_headway_m", "camera_corrected", "gt_headway_m"]].copy()
        shared["least_squares_fused"] = fused_test
    shared.to_csv(shared_path, index=False)
    print(f"added 'least_squares_fused' column to {shared_path}\n")

    # ---- plot: fused vs GT over time, test block only ----
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(test["time"], gt_test, color="blue", linewidth=1.2, label="Ground truth")
    ax.plot(test["time"], test["lidar_headway_m"], color="red", linestyle="--",
            linewidth=1, alpha=1, label="LiDAR alone")
    ax.plot(test["time"], test["camera_corrected"], color="#2ca02c", linestyle="--",
            linewidth=1, alpha=1, label="Camera alone")
    ax.plot(test["time"], fused_test, color="orange", linewidth=1.2, label="Least-squares fusion")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Headway (m)")
    ax.set_title(f"Fused Headway Estimate on Test Data")
    ax.legend(loc="lower right", framealpha=0.9)
    plt.tight_layout()
    plot_path = os.path.join(output_dir, "least_squares_test_plot.pdf")
    plt.savefig(plot_path, format="pdf", bbox_inches="tight")
    plt.close()

    print(f"Saved to {output_dir}/:")
    print(f"  least_squares_test_plot.pdf")
    print(f"  least_squares_results.csv")
    print(f"  least_squares_test_frames.csv")
    print(f"  least_squares_report.txt")


if __name__ == "__main__":
    main()
