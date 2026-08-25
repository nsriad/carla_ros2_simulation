#!/usr/bin/env python3
"""
usage:
    python3 fusion/plot_fusion_comparison.py \
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv

    # hide specific columns by name, e.g. raw sensors or one fusion method
    python3 fusion/plot_fusion_comparison.py \
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv \
        --skip lidar_headway_m camera_corrected mlp_mse_nodiff_fused

    # zoom in on the known spike region as a third panel
    python3 fusion/plot_fusion_comparison.py \
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv \
        --zoom_start 120 --zoom_end 128

    # rename a column's legend entry instead of the auto-generated label
    python3 fusion/plot_fusion_comparison.py \
        --comparison_csv ../data/multimodal_dataset_20260713_191320/processed_fusion/fusion_comparison.csv \
        --skip least_squares_fused mlp_mse_nodiff_fused cp_fused cp_fused_lower cp_fused_upper \
        --label mlp_mse_fused="MLP" mlp_mse_lag5_fused="MLP (w=5)" mlp_mse_lag10_fused="MLP (w=10)" \
        --zoom_start 120 --zoom_end 128
"""

import argparse
import itertools
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

# fixed styling for the raw sensor columns, everything else is auto-styled
KNOWN_COLUMNS = {
    "lidar_headway_m": ("LiDAR", "red", "--"),
    "camera_corrected": ("Camera", "#2ca02c", "--"),
}
NON_METHOD_COLUMNS = {"time", "gt_headway_m"}
AUTO_COLORS = ["purple", "orange", "darkgreen", "#ff00dd", "brown", "teal", "gold", "black"]


def label_from_column(col):
    # e.g. mlp_mse_lag5_fused -> "Mlp Mse Lag5"
    return col.replace("_fused", "").replace("_", " ").strip().title()


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--comparison_csv", required=True, help="fusion_comparison.csv")
    p.add_argument("--skip", nargs="+", default=[], help="column names to hide")
    p.add_argument("--label", nargs="+", default=[],
                   help="override a column's legend label, format: column=Text (e.g. mlp_mse_lag5_fused=\"Window 5\")")
    p.add_argument("--zoom_start", type=float, default=None, help="optional zoom window start (seconds)")
    p.add_argument("--zoom_end", type=float, default=None, help="optional zoom window end (seconds)")
    p.add_argument("--output_dir", default=None)
    return p.parse_args()


def build_methods(df, skip, label_overrides):
    methods = []
    colors = itertools.cycle(AUTO_COLORS)
    for col in df.columns:
        if col in NON_METHOD_COLUMNS:
            continue
        if col in skip:
            print(f"skipping {col} (--skip)")
            continue
        if col in KNOWN_COLUMNS:
            label, color, style = KNOWN_COLUMNS[col]
        else:
            label, color, style = label_from_column(col), next(colors), "--"
        if col in label_overrides:
            label = label_overrides[col]
        methods.append((col, label, color, style))
    return methods


def main():
    args = parse_args()
    output_dir = args.output_dir or os.path.dirname(args.comparison_csv)
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(args.comparison_csv).sort_values("time").reset_index(drop=True)
    print(f"loaded {len(df)} frames, columns: {list(df.columns)}\n")

    label_overrides = dict(item.split("=", 1) for item in args.label)
    methods = build_methods(df, args.skip, label_overrides)
    if not methods:
        print("nothing left to plot after skipping/missing columns.")
        return

    # figure 1 everything vs ground truth
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(df["time"], df["gt_headway_m"], color="blue", linestyle=":", linewidth=1, label="Ground truth", zorder=10)
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
    fig, ax = plt.subplots(figsize=(5, 5))
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

    # figure 3 zoomed-in window
    if args.zoom_start is not None and args.zoom_end is not None:
        fig, ax = plt.subplots(figsize=(5, 5))
        zoom = df[(df["time"] >= args.zoom_start) & (df["time"] <= args.zoom_end)]
        ax.plot(zoom["time"], zoom["gt_headway_m"], color="blue", linestyle=":", linewidth=1, label="Ground truth", zorder=10)
        for col, label, color, style in methods:
            ax.plot(zoom["time"], zoom[col], color=color, linestyle=style, linewidth=1, alpha=0.9, label=label)
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
