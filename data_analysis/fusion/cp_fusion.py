#!/usr/bin/env python3
"""
usage:
    python3 fusion/cp_fusion.py \\
        --merged_csv ../data/multimodal_dataset_20260713_191320/merged_cam_lid_gt.csv \\
        --alpha 0.1
"""

import argparse
import os
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--merged_csv", required=True)
    p.add_argument("--train_frac", type=float, default=0.5,
                   help="must match the other fusion scripts' --train_frac for a fair comparison")
    p.add_argument("--alpha", type=float, default=0.1, help="miscoverage rate, 0.1 = 90% target coverage")
    p.add_argument("--output_dir", default=None)
    return p.parse_args()


def cp_quantile(scores, alpha):
    # standard split-cp finite-sample correction
    n = len(scores)
    level = np.ceil((n + 1) * (1 - alpha)) / n
    level = min(level, 1.0)
    return np.quantile(scores, level, method="higher")


def coverage(estimate, q, gt):
    lower = estimate - q
    upper = estimate + q
    return np.mean((gt >= lower) & (gt <= upper))


def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.merged_csv), 'processed_fusion')
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(args.merged_csv).sort_values("time").reset_index(drop=True)
    print(f"loaded {len(df)} frames\n")

    # same time-block split as the other fusion scripts
    n_train = int(args.train_frac * len(df))
    calib = df.iloc[:n_train].reset_index(drop=True)
    test = df.iloc[n_train:].reset_index(drop=True)
    print(f"calibration fold = first {len(calib)} frames, test fold = last {len(test)} frames")
    print("(this split should match least_squares_fusion.py / train_mlp_fusion.py)\n")

    # per-sensor q, from the calibration fold
    sc_lidar = (calib["lidar_headway_m"] - calib["gt_headway_m"]).abs().values
    sc_cam = (calib["camera_corrected"] - calib["gt_headway_m"]).abs().values

    q_lidar = cp_quantile(sc_lidar, args.alpha)
    q_cam = cp_quantile(sc_cam, args.alpha)
    print(f"q_lidar  = {q_lidar:.3f} m")
    print(f"q_camera = {q_cam:.3f} m\n")

    # inverse-variance fusion weights, using q^2 as a variance stand-in
    var_lidar = q_lidar ** 2
    var_cam = q_cam ** 2
    w_lidar = (1 / var_lidar) / (1 / var_lidar + 1 / var_cam)
    w_cam = 1 - w_lidar
    print(f"weights: w_lidar = {w_lidar:.4f}, w_camera = {w_cam:.4f}\n")

    # fused estimate needs its own q, calibrated on the same fold
    fused_calib = w_lidar * calib["lidar_headway_m"] + w_cam * calib["camera_corrected"]
    sc_fused = (fused_calib - calib["gt_headway_m"]).abs().values
    q_fused = cp_quantile(sc_fused, args.alpha)
    print(f"q_fused  = {q_fused:.3f} m\n")

    # evaluate everything on the test fold
    fused_test = w_lidar * test["lidar_headway_m"] + w_cam * test["camera_corrected"]
    gt_test = test["gt_headway_m"].values

    results = []
    for name, est, q in [
        ("LiDAR alone", test["lidar_headway_m"].values, q_lidar),
        ("Camera alone (calibrated)", test["camera_corrected"].values, q_cam),
        ("CP inverse-variance fusion", fused_test.values, q_fused),
    ]:
        err = est - gt_test
        mae = np.mean(np.abs(err))
        rmse = np.sqrt(np.mean(err ** 2))
        cov = coverage(est, q, gt_test)
        results.append({"sensor": name, "MAE": mae, "RMSE": rmse, "q": q,
                         "coverage": cov, "target_coverage": 1 - args.alpha})

    results_df = pd.DataFrame(results)
    print("=" * 65)
    print("results on the test fold")
    print("=" * 65)
    print(results_df.to_string(index=False))

    # save
    results_df.to_csv(os.path.join(output_dir, "cp_fusion_results.csv"), index=False)

    with open(os.path.join(output_dir, "cp_fusion_report.txt"), "w") as f:
        f.write(f"alpha = {args.alpha} (target coverage = {1 - args.alpha:.0%})\n")
        f.write(f"q_lidar = {q_lidar:.4f}, q_camera = {q_cam:.4f}, q_fused = {q_fused:.4f}\n")
        f.write(f"weights: w_lidar = {w_lidar:.4f}, w_camera = {w_cam:.4f}\n\n")
        f.write(results_df.to_string(index=False))

    # write into the shared comparison file, same convention as the other fusion scripts
    col_name = "cp_fused"
    shared_path = os.path.join(output_dir, "fusion_comparison.csv")
    if os.path.exists(shared_path):
        shared = pd.read_csv(shared_path)
        if col_name in shared.columns:
            shared = shared.drop(columns=[col_name])
        new_col = pd.DataFrame({
            "time": test["time"].values,
            col_name: fused_test.values,
            "cp_fused_lower": fused_test.values - q_fused,
            "cp_fused_upper": fused_test.values + q_fused,
        })
        shared = shared.merge(new_col, on="time", how="outer")
    else:
        shared = test[["time", "lidar_headway_m", "camera_corrected", "gt_headway_m"]].copy()
        shared[col_name] = fused_test.values
        shared["cp_fused_lower"] = fused_test.values - q_fused
        shared["cp_fused_upper"] = fused_test.values + q_fused

    shared.to_csv(shared_path, index=False)
    print(f"\nadded '{col_name}' column (plus lower/upper interval bounds) to {shared_path}")


if __name__ == "__main__":
    main()
