#!/usr/bin/env python3
"""
usage:
    python3 fusion/train_mlp_fusion.py \
        --merged_csv ../data/multimodal_dataset_20260713_191320/merged_cam_lid_gt.csv \
        --loss huber --huber_delta 1.0

    python3 fusion/train_mlp_fusion.py \
        --merged_csv ../data/multimodal_dataset_20260713_191320/merged_cam_lid_gt.csv \
        --loss mse
"""

import argparse
import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--merged_csv", required=True)
    p.add_argument("--train_frac", type=float, default=0.5,
                   help="must match least_squares_fusion.py's --train_frac for a fair comparison")
    p.add_argument("--loss", choices=["mse", "huber"], default="huber")
    p.add_argument("--no_diff", action="store_true",
                   help="exclude the |lidar - camera| feature, to test whether it actually helps")
    p.add_argument("--huber_delta", type=float, default=1.0,
                   help="huber's switch point in meters: quadratic below this, linear above it")
    p.add_argument("--hidden_dims", default="16,8", help="comma-separated hidden layer sizes")
    p.add_argument("--epochs", type=int, default=50000)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output_dir", default=None)
    return p.parse_args()


class FusionMLP(nn.Module):
    def __init__(self, n_inputs, hidden_dims):
        super().__init__()
        layers = []
        prev_size = n_inputs
        for h in hidden_dims:
            layers.append(nn.Linear(prev_size, h))
            layers.append(nn.ReLU())
            prev_size = h
        layers.append(nn.Linear(prev_size, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        out = self.net(x)
        return out.squeeze(-1)


def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.merged_csv), 'processed_fusion')
    os.makedirs(output_dir, exist_ok=True)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # load and sort by time, same as least_squares_fusion.py
    df = pd.read_csv(args.merged_csv).sort_values("time").reset_index(drop=True)

    # just one extra feature: how much the two sensors disagree
    if args.no_diff:
        print("running without the diff feature, for comparison against the version that has it\n")
    else:
        df["diff"] = (df["lidar_headway_m"] - df["camera_corrected"]).abs()

    # same time-block split as least_squares_fusion.py: train on the first half, test on the second
    n_train = int(args.train_frac * len(df))
    train = df.iloc[:n_train].reset_index(drop=True)
    test = df.iloc[n_train:].reset_index(drop=True)
    print(f"train = first {len(train)} frames, test = last {len(test)} frames")
    print("(this split should match least_squares_fusion.py's split for a fair comparison)\n")

    feature_cols = ["lidar_headway_m", "camera_corrected"] if args.no_diff else ["lidar_headway_m", "camera_corrected", "diff"]

    # standardize using train stats only, so test never leaks into the scaling
    feat_mean = train[feature_cols].mean()
    feat_std = train[feature_cols].std().replace(0, 1.0)

    x_train = ((train[feature_cols] - feat_mean) / feat_std).values.astype(np.float32)
    x_test = ((test[feature_cols] - feat_mean) / feat_std).values.astype(np.float32)

    # normalize the target too, same idea as the input features
    y_mean = train["gt_headway_m"].mean()
    y_std = train["gt_headway_m"].std()
    y_train = ((train["gt_headway_m"] - y_mean) / y_std).values.astype(np.float32)

    x_train = torch.tensor(x_train)
    y_train = torch.tensor(y_train)
    x_test = torch.tensor(x_test)

    hidden_dims = [int(h) for h in args.hidden_dims.split(",")]
    model = FusionMLP(n_inputs=len(feature_cols), hidden_dims=hidden_dims)

    if args.loss == "huber":
        criterion = nn.HuberLoss(delta=args.huber_delta)
        print(f"using huber loss (delta={args.huber_delta}m): caps how much a single bad frame can pull the fit\n")
    else:
        criterion = nn.MSELoss()
        print("using mse loss: every error gets squared, so big misses count a lot more\n")

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    model.train()
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        pred = model(x_train)
        loss = criterion(pred, y_train)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 250 == 0 or epoch == 0:
            print(f"  epoch {epoch + 1}/{args.epochs}  train loss = {loss.item():.6f}")

    # evaluate on the test frames only, never seen during training
    model.eval()
    with torch.no_grad():
        pred_test = model(x_test).numpy()
    pred_test = pred_test * y_std + y_mean   # undo the normalization

    gt_test = test["gt_headway_m"].values
    error = pred_test - gt_test
    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))

    lidar_error = test["lidar_headway_m"].values - gt_test
    lidar_mae = np.mean(np.abs(lidar_error))
    lidar_rmse = np.sqrt(np.mean(lidar_error ** 2))

    cam_error = test["camera_corrected"].values - gt_test
    cam_mae = np.mean(np.abs(cam_error))
    cam_rmse = np.sqrt(np.mean(cam_error ** 2))

    col_name = f"mlp_{args.loss}_nodiff_fused" if args.no_diff else f"mlp_{args.loss}_fused"
    results = pd.DataFrame([
        {"sensor": "LiDAR alone", "MAE": lidar_mae, "RMSE": lidar_rmse},
        {"sensor": "Camera alone (calibrated)", "MAE": cam_mae, "RMSE": cam_rmse},
        {"sensor": col_name, "MAE": mae, "RMSE": rmse},
    ])
    print("\n" + "=" * 55)
    print(f"results on test frames (loss = {args.loss})")
    print("=" * 55)
    print(results.to_string(index=False))

    # write into the shared comparison file, adding a new column each time this script runs
    shared_path = os.path.join(output_dir, "fusion_comparison.csv")
    if os.path.exists(shared_path):
        shared = pd.read_csv(shared_path)
    else:
        shared = test[["time", "lidar_headway_m", "camera_corrected", "gt_headway_m"]].copy()

    # align by time and assign directly, this either creates the column or
    # overwrites it cleanly, no merge, no suffixes, no _x/_y duplicates possible
    pred_series = pd.Series(pred_test, index=test["time"].values)
    shared = shared.set_index("time")
    shared[col_name] = pred_series
    shared = shared.reset_index()

    shared.to_csv(shared_path, index=False)
    print(f"\nadded '{col_name}' column to {shared_path}")

    with open(os.path.join(output_dir, f"{col_name}_report.txt"), "w") as f:
        f.write(f"loss: {args.loss} (delta={args.huber_delta})\n")
        f.write(f"hidden dims: {hidden_dims}\n")
        f.write(f"features: {feature_cols}\n\n")
        f.write(results.to_string(index=False))


if __name__ == "__main__":
    main()
