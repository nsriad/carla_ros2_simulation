#!/usr/bin/env python3
"""
Calibrate camera headway estimate against ground truth, for ONE scenario:
town04_leader_50_multimodal_dataset_20260618_102918

Just three inputs:
  1. Ground truth: data/headway_csv/headway_log_20260618_102918.csv
  2. Camera estimate: .../processed_camera/camera_headway_estimates.csv
  3. Camera timestamps: .../processed_camera/camera_timestamps.csv

Steps:
  1. Merge camera_headway_estimates.csv (frame, camera_headway_m) with
     camera_timestamps.csv (frame_id, timestamp, timestamp_normalized) by frame number
  2. Merge that against ground truth by nearest timestamp
  3. Split into calibration (20%) / evaluation (80%)
  4. Fit a linear correction: d_gt = a * d_cam + b, using calibration set only
  5. Apply to evaluation set, report MAE/RMSE before and after correction

USAGE:
    python3 calibrate_single_scenario.py \\
        --gt_csv ~/Nazmus_Shakib/Summer_26/carla_simulation_ws/data/headway_csv/headway_log_20260618_102918.csv \\
        --cam_dir ~/Nazmus_Shakib/Summer_26/carla_simulation_ws/data/town04_leader_50_multimodal_dataset_20260618_102918/processed_camera

If the script can't find the right columns in your ground truth CSV, it will
print the columns it found so you can tell me the correct names.
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 16,
    "font.size": 14,
    "legend.fontsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
})


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gt_csv", required=True, help="Path to headway_log_....csv")
    p.add_argument("--cam_dir", required=True, help="Path to .../processed_camera/")
    p.add_argument("--gt_time_col", default=None, help="Override if auto-detect fails")
    p.add_argument("--gt_dist_col", default=None, help="Override if auto-detect fails")
    p.add_argument("--output_dir", default=None,
                    help="Where to save results. Default: same as --cam_dir "
                         "(results land directly inside processed_camera/)")
    return p.parse_args()


def extract_numeric_id(s):
    digits = "".join(ch for ch in str(s) if ch.isdigit())
    return int(digits) if digits else None


def autodetect(columns, candidates):
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def main():
    args = parse_args()
    output_dir = args.output_dir or args.cam_dir
    os.makedirs(output_dir, exist_ok=True)

    # load all the three files
    gt = pd.read_csv(args.gt_csv)
    cam_est = pd.read_csv(os.path.join(args.cam_dir, "camera_headway_estimates_0.3_excl40.csv"))
    cam_ts = pd.read_csv(os.path.join(args.cam_dir, "camera_timestamps.csv"))

    print(f"Ground truth columns : {list(gt.columns)}")
    print(f"Camera est columns   : {list(cam_est.columns)}")
    print(f"Camera ts columns    : {list(cam_ts.columns)}\n")

    # figure out GT column names
    tcol = args.gt_time_col or autodetect(gt.columns, ["timestamp", "time", "time_sec", "t", "sec", "stamp"])
    dcol = args.gt_dist_col or autodetect(gt.columns, ["headway", "space_headway", "distance",
                                                          "gt_headway", "ground_truth_headway", "headway_m"])
    if tcol is None or dcol is None:
        print("Could not auto-detect ground truth time/distance columns.")
        print(f"Found columns: {list(gt.columns)}")
        print("Re-run with --gt_time_col and --gt_dist_col set explicitly.")
        return

    print(f"Using GT time column: '{tcol}', GT distance column: '{dcol}'\n")

    # merge camera estimates with camera timestamps by frame number
    cam_est["frame_num"] = cam_est["frame"].apply(extract_numeric_id)
    frame_id_col = "frame_id" if "frame_id" in cam_ts.columns else cam_ts.columns[0]
    cam_ts["frame_num"] = cam_ts[frame_id_col].apply(extract_numeric_id)

    cam = pd.merge(cam_est, cam_ts, on="frame_num", how="inner")
    print(f"Matched {len(cam)} / {len(cam_est)} camera frames to timestamps.")

    time_col_cam = "timestamp_normalized" if "timestamp_normalized" in cam.columns else "timestamp"

    # merge against ground truth by nearest timestamp
    cam_sorted = cam.sort_values(time_col_cam).reset_index(drop=True)
    gt_sorted = gt.sort_values(tcol).reset_index(drop=True)

    # normalize GT time to start at 0 to match camera's normalized time, if needed
    if time_col_cam == "timestamp_normalized":
        gt_sorted["_t_norm"] = gt_sorted[tcol] - gt_sorted[tcol].iloc[0]
        gt_key = "_t_norm"
    else:
        gt_key = tcol

    merged = pd.merge_asof(
        cam_sorted, gt_sorted,
        left_on=time_col_cam, right_on=gt_key,
        direction="nearest", tolerance=0.15
    )
    merged = merged.dropna(subset=[dcol])
    print(f"Matched {len(merged)} camera frames to ground truth (within 150ms).\n")

    print("Sanity check (first 5 rows):")
    print(merged[["frame", time_col_cam, gt_key, "camera_headway_m", dcol]].head(5).to_string(index=False))
    print()

    if len(merged) < 20:
        print("Too few matched frames to calibrate reliably. Check timestamp alignment above.")
        return

    x = merged["camera_headway_m"].values.astype(float)
    y = merged[dcol].values.astype(float)

    # calibration / evaluation split (simple random 20/80)
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(x))
    n_calib = int(0.2 * len(x))
    calib_idx, eval_idx = idx[:n_calib], idx[n_calib:]

    x_calib, y_calib = x[calib_idx], y[calib_idx]
    x_eval, y_eval = x[eval_idx], y[eval_idx]

    # fit linear correction: d_gt = a * d_cam + b
    A = np.vstack([x_calib, np.ones_like(x_calib)]).T
    (a, b), _, _, _ = np.linalg.lstsq(A, y_calib, rcond=None)
    print(f"Fitted correction: d_gt = {a:.4f} * d_cam + {b:.4f}")
    print(f"(fit on {len(x_calib)} calibration frames, evaluated on {len(x_eval)} held-out frames)\n")

    y_eval_corrected = a * x_eval + b

    mae_raw = np.mean(np.abs(x_eval - y_eval))
    mae_corr = np.mean(np.abs(y_eval_corrected - y_eval))
    rmse_raw = np.sqrt(np.mean((x_eval - y_eval) ** 2))
    rmse_corr = np.sqrt(np.mean((y_eval_corrected - y_eval) ** 2))

    print(f"BEFORE correction: MAE = {mae_raw:.3f} m   RMSE = {rmse_raw:.3f} m")
    print(f"AFTER  correction: MAE = {mae_corr:.3f} m   RMSE = {rmse_corr:.3f} m")

    # flag worst outliers (largest single-frame errors) on the full set
    all_corrected = a * x + b
    all_err = np.abs(all_corrected - y)
    merged["camera_corrected"] = all_corrected
    merged["abs_error"] = all_err
    worst = merged.sort_values("abs_error", ascending=False).head(5)
    print(f"\nWorst 5 frames by corrected error (check these images):")
    print(worst[["frame", time_col_cam, "camera_headway_m", "camera_corrected", dcol, "abs_error"]]
          .to_string(index=False))

    # save results
    out_csv = os.path.join(output_dir, "camera_calibrated_0.3_excl40.csv")
    merged[["frame", time_col_cam, "camera_headway_m", "camera_corrected", dcol, "abs_error"]].to_csv(
        out_csv, index=False
    )

    with open(os.path.join(output_dir, "calibration_report_0.3_excl40.txt"), "w") as f:
        f.write(f"Fitted correction: d_gt = {a:.4f} * d_cam + {b:.4f}\n")
        f.write(f"Calibration frames: {len(x_calib)} | Evaluation frames: {len(x_eval)}\n\n")
        f.write(f"BEFORE correction: MAE={mae_raw:.3f}m RMSE={rmse_raw:.3f}m\n")
        f.write(f"AFTER  correction: MAE={mae_corr:.3f}m RMSE={rmse_corr:.3f}m\n\n")
        f.write("Worst 5 frames:\n")
        f.write(worst[["frame", "camera_headway_m", "camera_corrected", dcol, "abs_error"]].to_string(index=False))

    # scatter plot: before / after
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    lims = [0, max(y_eval.max(), x_eval.max()) * 1.05]
    axes[0].scatter(x_eval, y_eval, s=12, alpha=0.6, c="#e76f51")
    axes[0].plot(lims, lims, "k--", linewidth=1)
    axes[0].set_xlabel("Camera raw (m)"); axes[0].set_ylabel("Ground truth (m)")
    axes[0].set_title(f"Before (MAE={mae_raw:.2f}m)")

    axes[1].scatter(y_eval_corrected, y_eval, s=12, alpha=0.6, c="#4a7fb5")
    axes[1].plot(lims, lims, "k--", linewidth=1)
    axes[1].set_xlabel("Camera corrected (m)"); axes[1].set_ylabel("Ground truth (m)")
    axes[1].set_title(f"After (MAE={mae_corr:.2f}m)")

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "leader_50_calibration_0.3_excl40.pdf")
    plt.savefig(plot_path, format='pdf', bbox_inches="tight")
    plt.close()

    # residual vs time
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    residual = merged["camera_corrected"] - merged[dcol]
    ax2.scatter(merged[time_col_cam], residual, s=10, alpha=0.5, c="#5a5a8a")
    ax2.axhline(0, color="k", linestyle="--", linewidth=1)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Residual (m)")
    ax2.set_title("Residual over time")
    plt.tight_layout()
    residual_path = os.path.join(output_dir, "leader_50_residual_vs_time_0.3_excl40.pdf")
    plt.savefig(residual_path, format='pdf', bbox_inches="tight")
    plt.close()

    print(f"\nSaved to {output_dir}/:")
    print(f"  leader_50_calibration_0.3_excl40.pdf       <- before/after scatter, look at this first")
    print(f"  leader_50_residual_vs_time_0.3_excl40.pdf  <- checks if error is time-correlated")
    print(f"  camera_calibrated_0.3_excl40.csv           <- all frames with corrected values + error")
    print(f"  calibration_report_0.3_excl40.txt")

if __name__ == "__main__":
    main()
