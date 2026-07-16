#!/usr/bin/env python3
import os
import sys, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('pdf')   # avoids dvipng dependency when text.usetex=True
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

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
        print("Usage: python3 headway_analysis.py <DATETIME>")
        sys.exit(1)

    DATETIME = sys.argv[1]

    matches = glob.glob(f'../data/*{DATETIME}')
    if not matches:
        print(f"No dataset folder found matching *{DATETIME}")
        sys.exit(1)
    run_dir = matches[0]

    # input raw csv and output directory inside the run's folder
    csv_path = f'../data/headway_csv/headway_log_{DATETIME}.csv'
    output_dir = os.path.join(run_dir, 'processed_headway')

    # create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading headway log from: {csv_path}")
    df = pd.read_csv(csv_path)

    # normalize time so the graphs start exactly at t=0
    df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

    calib_files = glob.glob(os.path.join(run_dir, 'processed_camera', 'camera_calibrated_*.csv'))
    calibrated_path = max(calib_files, key=os.path.getmtime) if calib_files else None
    
    if os.path.exists(calibrated_path):
        print("Loading calibrated camera estimates...")
        df_cam = pd.read_csv(calibrated_path)

        time_col = 'timestamp_normalized' if 'timestamp_normalized' in df_cam.columns else 'timestamp'
        if time_col == 'timestamp':
            t0 = df['timestamp'].iloc[0]
            df_cam['time'] = df_cam['timestamp'] - t0
        else:
            df_cam['time'] = df_cam[time_col]  # already normalized to its own t=0
    else:
        df_cam = None
        print(f"Warning: Missing {calibrated_path} — run camera_calibrate.py first")


    # split into valid/missing lidar rows
    valid = df[(df['lidar_headway_m'] >= 0) & (df['gt_headway_m'] >= 0)].copy()

    # per-sample estimation error where both measurements are available
    valid['error'] = valid['lidar_headway_m'] - valid['gt_headway_m']

    # summary statistics
    rmse = np.sqrt((valid['error'] ** 2).mean())
    mae  = valid['error'].abs().mean()

    print(f"Total samples: {len(df)}")
    print(f"Valid LiDAR samples: {len(valid)} ({100.0 * len(valid) / len(df):.1f}%)")
    print(f"MAE: {mae:.4f} m")
    print(f"RMSE: {rmse:.4f} m")

    # save merged sensor data
    if df_cam is not None:

        df_cam_for_merge = df_cam.drop(columns=['gt_headway_m'], errors='ignore')
        merged_cam_lid_gt = pd.merge_asof(
            df_cam_for_merge.sort_values('time'),
            valid[['time', 'lidar_headway_m', 'gt_headway_m']].sort_values('time'),
            on='time', direction='nearest', tolerance=0.1
        )
        merged_cam_lid_gt = merged_cam_lid_gt.dropna(subset=['lidar_headway_m'])
        merged_out = merged_cam_lid_gt[['time', 'camera_corrected', 'lidar_headway_m', 'gt_headway_m']]

        merged_csv_path = os.path.join(run_dir, 'merged_cam_lid_gt.csv')
        merged_out.to_csv(merged_csv_path, index=False)
        print(f"Saved merged sensor data for fusion: {merged_csv_path} "
              f"({len(merged_out)} time-aligned frames)")
    else:
        print("Skipping fusion export: df_cam is None (camera_calibrated CSV not found)")

    # headway time series

    fig1, ax1 = plt.subplots(figsize=(10, 4))

    ax1.plot(df['time'], df['gt_headway_m'].where(df['gt_headway_m'] >= 0), color='blue', linewidth=1.0, label=r'Ground Truth $d_{\mathrm{gt}}$')
    ax1.plot(valid['time'], valid['lidar_headway_m'], color='red', linestyle='--',linewidth=1.0, alpha=1, label=r'LiDAR Estimate $\hat{d}$')
    # time-sync cam data
    if df_cam is not None:
        # the missing frames will naturally show up as visual gaps in the line!
        ax1.plot(df_cam['time'], df_cam['camera_corrected'],
          color="#2ca02c", linewidth=0.6, alpha=0.5,
          marker='.', markersize=3, markeredgewidth=0,
          label=r'Camera Estimate')

    # gap_patch = mpatches.Patch(color='#ffcccc', alpha=0.7, label=r'Detection Lost')
    # handles, labels = ax1.get_legend_handles_labels()
    # ax1.legend(handles + [gap_patch], labels + [gap_patch.get_label()], loc='upper right', framealpha=0.9)
    ax1.legend(loc='upper right', framealpha=0.9)

    ax1.set_title(r'\textbf{Space Headway Over Time}')
    ax1.set_xlabel(r'Time ($s$)')
    ax1.set_ylabel(r'Space Headway ($m$)')
    ax1.set_xlim(df['time'].min(), df['time'].max())
    ax1.set_ylim(bottom=0)
    ax1.grid(True, linestyle='--', alpha=0.6)

    plot1_path = os.path.join(output_dir, 'headway_time_series_cam.pdf')
    fig1.savefig(plot1_path, format='pdf', bbox_inches='tight')
    print(f"Saved: {plot1_path}")
    plt.close(fig1)

    # estimation error trace 

    fig2, ax2 = plt.subplots(figsize=(10, 4))

    ax2.axhline(0,      color='black',     linewidth=0.8, linestyle='--', zorder=1)
    ax2.axhline( rmse,  color='firebrick', linewidth=1.0, linestyle=':',  zorder=2, label=rf'$\pm$RMSE $= {rmse:.3f}$ m')
    ax2.axhline(-rmse,  color='firebrick', linewidth=1.0, linestyle=':',  zorder=2)
    ax2.fill_between(valid['time'], -rmse, rmse, color='firebrick', alpha=0.08, zorder=0)

    ax2.plot(valid['time'], valid['error'], color='#2e8b57', linewidth=1.5, alpha=0.85, label=r'$e = \hat{d} - d_{\mathrm{gt}}$')

    ax2.set_title(r'\textbf{Estimation Error}')
    ax2.set_xlabel(r'Time ($s$)')
    ax2.set_ylabel(r'Error ($m$)')
    ax2.set_xlim(df['time'].min(), df['time'].max())
    ax2.legend(loc='upper right', framealpha=0.9)
    ax2.grid(True, linestyle='--', alpha=0.6)

    plot2_path = os.path.join(output_dir, 'headway_error_trace_cam.pdf')
    fig2.savefig(plot2_path, format='pdf', bbox_inches='tight')
    print(f"Saved: {plot2_path}")
    plt.close(fig2)

    # lidar vs gt scatter

    fig3, ax3 = plt.subplots(figsize=(5, 5))

    ax3.scatter(valid['gt_headway_m'], valid['lidar_headway_m'], s=4, alpha=0.35, color='steelblue', zorder=2)

    lim_max = max(valid['gt_headway_m'].max(), valid['lidar_headway_m'].max()) * 1.05
    ax3.plot([0, lim_max], [0, lim_max], 'k--', linewidth=1.0, label=r'Ideal ($\hat{d} = d_{\mathrm{gt}}$)', zorder=3)
    ax3.fill_between([0, lim_max],[0 - rmse, lim_max - rmse],[0 + rmse, lim_max + rmse],color='firebrick', alpha=0.10, label=rf'$\pm$RMSE $= {rmse:.3f}$ m', zorder=1)

    ax3.set_title(r'\textbf{LiDAR vs.\ Ground Truth}')
    ax3.set_xlabel(r'Ground Truth $d_{\mathrm{gt}}$ ($m$)')
    ax3.set_ylabel(r'LiDAR Estimate $\hat{d}$ ($m$)')
    ax3.set_xlim(0, lim_max)
    ax3.set_ylim(0, lim_max)
    ax3.set_aspect('equal', adjustable='box')
    ax3.legend(loc='upper left', framealpha=0.9)
    ax3.grid(True, linestyle='--', alpha=0.6)

    plot3_path = os.path.join(output_dir, headway_scatter_cam.pdf')
    fig3.savefig(plot3_path, format='pdf', bbox_inches='tight')
    print(f"Saved: {plot3_path}")
    plt.close(fig3)

    plt.show()

if __name__ == '__main__':
    main()
