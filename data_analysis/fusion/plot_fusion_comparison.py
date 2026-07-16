#!/usr/bin/env python3
"""
use the --skip-* flags to hide a method you don't want in the plot,
or leave everything on to see all of them at once.

usage:
    python3 fusion/plot_fusion_comparison.py \\
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv

    # hide lidar and camera, just compare the fusion methods against each other
    python3 fusion/plot_fusion_comparison.py \\
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv \\
        --skip-lidar --skip-camera

    # zoom in on the known spike region as a third panel
    python3 fusion/plot_fusion_comparison.py \\
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv \\
        --zoom_start 120 --zoom_end 128
"""

import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

# global LaTeX config
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 18,
    "font.size": 16,
    "legend.fontsize": 10,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
})


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--comparison_csv", required=True, help="fusion_comparison.csv")
    p.add_argument("--skip-lidar", action="store_true")
    p.add_argument("--skip-camera", action="store_true")
    p.add_argument("--skip-least-squares", action="store_true")
    p.add_argument("--skip-mlp-mse", action="store_true")
    p.add_argument("--skip-mlp-huber", action="store_true")
    p.add_argument("--zoom_start", type=float, default=None, help="optional zoom window start (seconds)")
    p.add_argument("--zoom_end", type=float, default=None, help="optional zoom window end (seconds)")
    p.add_argument("--output_dir", default=None)
    return p.parse_args()
 
 
def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.dirname(args.comparison_csv)
    os.makedirs(output_dir, exist_ok=True)
 
    df = pd.read_csv(args.comparison_csv).sort_values("time").reset_index(drop=True)
    print(f"loaded {len(df)} frames, columns: {list(df.columns)}\n")
 
    # each entry: (flag, column name, plot label, color, linestyle)
    method_configs = [
        (args.skip_lidar, "lidar_headway_m",   "LiDAR", "red",     "--"),
        (args.skip_camera, "camera_corrected",  "Camera", "#2ca02c", ":"),
        (args.skip_least_squares, "least_squares_fused", "Least-squares fusion", "orange",  "-"),
        (args.skip_mlp_mse, "mlp_mse_fused", "MLP",     "purple",  "-"),
        # (args.skip_mlp_huber, "mlp_huber_fused", "MLP (Huber loss)",   "brown",   "-"),
    ]
 
    # only keep methods that aren't skipped and actually have a column in the csv
    methods = []
    for skip, col, label, color, style in method_configs:
        if skip:
            print(f"skipping {label} (--skip flag)")
            continue
        if col not in df.columns:
            print(f"skipping {label} ('{col}' not found in csv -- run that script first)")
            continue
        methods.append((col, label, color, style))
 
    if not methods:
        print("nothing left to plot after skipping/missing columns.")
        return
 
    # figure 1 everything vs ground truth
    fig, ax = plt.subplots(figsize=(6, 5.5))
    ax.plot(df["time"], df["gt_headway_m"], color="blue", linewidth=1.5, label="Ground truth", zorder=10)
    for col, label, color, style in methods:
        ax.plot(df["time"], df[col], color=color, linestyle=style, linewidth=1, alpha=0.8, label=label)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Headway (m)")
    ax.set_title("All methods vs ground truth")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()
    main_path = os.path.join(output_dir, "fusion_comparison_main.pdf")
    plt.savefig(main_path, format="pdf", bbox_inches="tight")
    plt.close()
 
    # figure 2
    fig, ax = plt.subplots(figsize=(6, 5.5))
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    for col, label, color, style in methods:
        residual = df[col] - df["gt_headway_m"]
        ax.plot(df["time"], residual, color=color, linestyle=style, linewidth=1, alpha=0.8, label=label)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Residual (m)")
    ax.set_title("Residual over time")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()
    residual_path = os.path.join(output_dir, "fusion_comparison_residual.pdf")
    plt.savefig(residual_path, format="pdf", bbox_inches="tight")
    plt.close()
 
    print(f"\nsaved: {main_path}")
    print(f"saved: {residual_path}")
 
    # figure 3 zoomed-in window ----
    if args.zoom_start is not None and args.zoom_end is not None:
        fig, ax = plt.subplots(figsize=(6, 5.5))
        zoom = df[(df["time"] >= args.zoom_start) & (df["time"] <= args.zoom_end)]
        ax.plot(zoom["time"], zoom["gt_headway_m"], color="blue", linewidth=1.5, label="Ground truth", zorder=10)
        for col, label, color, style in methods:
            ax.plot(zoom["time"], zoom[col], color=color, linestyle=style, linewidth=1.2, alpha=0.9, label=label)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Headway (m)")
        ax.set_title(f"Zoomed in: t = {args.zoom_start} to {args.zoom_end}s")
        ax.legend(loc="best", framealpha=0.9)
        plt.tight_layout()
        zoom_path = os.path.join(output_dir, "fusion_comparison_zoom.pdf")
        plt.savefig(zoom_path, format="pdf", bbox_inches="tight")
        plt.close()
        print(f"saved: {zoom_path}")
 
 
if __name__ == "__main__":
    main()
