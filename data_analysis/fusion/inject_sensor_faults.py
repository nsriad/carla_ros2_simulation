#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd

def parse_args():
    p = argparse.ArgumentParser(description="add noise, missing data, and distribution shift to a merged headway csv")
    p.add_argument("--merged_csv", required=True, help="clean merged_cam_lid_gt csv to corrupt")
    p.add_argument("--output_csv", required=True, help="where to save the corrupted copy")
    p.add_argument("--seed", type=int, default=42)

    # missing data. flip an already-valid reading to the -1.0 sentinel
    p.add_argument("--dropout_prob_camera", type=float, default=0.0, help="fraction of camera rows to drop, 0-1")
    p.add_argument("--dropout_prob_lidar", type=float, default=0.0, help="fraction of lidar rows to drop, 0-1")

    # noise, random jitter added on top of a valid reading
    p.add_argument("--noise_std_camera", type=float, default=0.0, help="gaussian noise std in meters, camera")
    p.add_argument("--noise_std_lidar", type=float, default=0.0, help="gaussian noise std in meters, lidar")

    # distribution shift, a bias that ramps from 0 up to the given value across the run
    p.add_argument("--bias_drift_camera", type=float, default=0.0, help="camera bias at end of run, meters")
    p.add_argument("--bias_drift_lidar", type=float, default=0.0, help="lidar bias at end of run, meters")

    return p.parse_args()

def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    df = pd.read_csv(args.merged_csv)
    n = len(df)

    # only touch rows that were actually valid to begin with
    cam_valid = df['camera_valid'] == 1
    lidar_valid = df['lidar_valid'] == 1

    # distribution shift. ramps from 0 at the start to the target bias at the end,
    # a slow drift rather than a fixed offset from frame one
    ramp = np.linspace(0, 1, n)
    df.loc[cam_valid, 'camera_corrected'] += ramp[cam_valid.values] * args.bias_drift_camera
    df.loc[lidar_valid, 'lidar_headway_m'] += ramp[lidar_valid.values] * args.bias_drift_lidar

    # noise, random jitter added on top of a valid reading
    if args.noise_std_camera > 0:
        df.loc[cam_valid, 'camera_corrected'] += rng.normal(0, args.noise_std_camera, cam_valid.sum())
    if args.noise_std_lidar > 0:
        df.loc[lidar_valid, 'lidar_headway_m'] += rng.normal(0, args.noise_std_lidar, lidar_valid.sum())

    # missing data, randomly drop some currently-valid readings to the sentinel
    if args.dropout_prob_camera > 0:
        drop = cam_valid & (rng.random(n) < args.dropout_prob_camera)
        df.loc[drop, 'camera_corrected'] = -1.0
        df.loc[drop, 'camera_valid'] = 0
    if args.dropout_prob_lidar > 0:
        drop = lidar_valid & (rng.random(n) < args.dropout_prob_lidar)
        df.loc[drop, 'lidar_headway_m'] = -1.0
        df.loc[drop, 'lidar_valid'] = 0

    df.to_csv(args.output_csv, index=False)
    print(f"saved: {args.output_csv}")
    print(f"camera valid: {df['camera_valid'].sum()}/{n} ({100 * df['camera_valid'].sum() / n:.1f}%)")
    print(f"lidar valid: {df['lidar_valid'].sum()}/{n} ({100 * df['lidar_valid'].sum() / n:.1f}%)")

if __name__ == '__main__':
    main()
