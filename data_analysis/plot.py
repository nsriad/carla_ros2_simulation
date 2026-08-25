#!/usr/bin/env python3
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('pdf')
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 plot_ml_prediction.py <DATETIME>")
        sys.exit(1)

    DATETIME = sys.argv[1]

    # reads from data/
    ml_log_path = f'../data/ml_inference_log_{DATETIME}.csv'
    print(f"Loading ML fusion predictions from: {ml_log_path}")
    df_ml = pd.read_csv(ml_log_path).sort_values('timestamp').reset_index(drop=True)

    # normalize time so the plot starts at t=0
    df_ml['time'] = df_ml['timestamp'] - df_ml['timestamp'].iloc[0]

    error = df_ml['predicted_headway_m'] - df_ml['gt_headway_m']
    rmse = np.sqrt((error ** 2).mean())
    mae = error.abs().mean()
    print(f"Predictions: {len(df_ml)} | MAE: {mae:.4f} m | RMSE: {rmse:.4f} m")

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(df_ml['time'], df_ml['gt_headway_m'], color='blue', linewidth=1.0,
             label=r'Ground Truth $d_{\mathrm{gt}}$')
    ax.plot(df_ml['time'], df_ml['predicted_headway_m'], color='#e07a3e', linestyle='--',
             linewidth=1.2, marker='.', markersize=4, markeredgewidth=0,
             label=r'ML Fused Prediction $\hat{d}$')

    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_title(r'\textbf{ML Fused Prediction vs.\ Ground Truth Over Time}')
    ax.set_xlabel(r'Time ($s$)')
    ax.set_ylabel(r'Space Headway ($m$)')
    ax.set_xlim(df_ml['time'].min(), df_ml['time'].max())
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle='--', alpha=0.6)

    # saved directly under data/
    plot_path = f'../data/headway_time_series_ml_{DATETIME}.pdf'
    fig.savefig(plot_path, format='pdf', bbox_inches='tight')
    print(f"Saved: {plot_path}")
    plt.close(fig)

if __name__ == '__main__':
    main()
