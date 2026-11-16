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
    "legend.fontsize": 8,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
})

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 headway_analysis.py <DATETIME>")
        sys.exit(1)

    DATETIME = sys.argv[1]
    cam_subdir = sys.argv[2] if len(sys.argv) > 2 else 'processed_camera'
    suffix = '' if cam_subdir == 'processed_camera' else '_' + cam_subdir.replace('processed_camera_', '')

    matches = glob.glob(f'../data/*{DATETIME}')
    if matches:
        run_dir = matches[0]
    else:
        # no bag folder for this session when record:=false
        # somewhere to save the plot
        run_dir = f'../data/run_{DATETIME}'
        print(f"No dataset folder for {DATETIME} (record:=false run), using {run_dir}")

    # input raw csv and output directory inside the run's folder
    csv_path = f'../data/headway_csv/headway_log_{DATETIME}.csv'
    output_dir = os.path.join(run_dir, 'processed_headway')

    # create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading headway log from: {csv_path}")
    df = pd.read_csv(csv_path)

    # normalize time so the graphs start exactly at t=0
    df['time'] = df['timestamp'] - df['timestamp'].iloc[0]

    calib_files = glob.glob(os.path.join(run_dir, cam_subdir, 'camera_calibrated_*.csv'))
    calibrated_path = max(calib_files, key=os.path.getmtime) if calib_files else None
    
    if calibrated_path is not None:
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
        print(f"Warning: Missing {calibrated_path}. Run camera_calibrate.py first")

    # live-logged camera + ml fused predictions, same session, already calibrated —
    # this is what actually powers the plot and stats below, no bag needed
    cam_log_path = f'../data/headway_csv/camera_headway_log_{DATETIME}.csv'
    df_cam_live = pd.read_csv(cam_log_path) if os.path.exists(cam_log_path) else None
    if df_cam_live is not None:
        df_cam_live['time'] = df_cam_live['timestamp'] - df['timestamp'].iloc[0]

    # ml fused prediction, if this session logged one, same folder as the other logs
    ml_log_path = f'../data/headway_csv/ml_inference_log_{DATETIME}.csv'
    if os.path.exists(ml_log_path):
        print("Loading ML fused predictions...")
        df_ml = pd.read_csv(ml_log_path)
        df_ml['time'] = df_ml['timestamp'] - df['timestamp'].iloc[0]
    else:
        df_ml = None
        print(f"Note: no {ml_log_path}")

    # split into valid/missing lidar rows
    valid = df[(df['lidar_headway_m'] >= 0) & (df['gt_headway_m'] >= 0)].copy()

    # per-sample estimation error where both measurements are available
    valid['error'] = valid['lidar_headway_m'] - valid['gt_headway_m']

    # score every sensor from when the ml node started, so all three cover the same window
    t_start = df_ml['timestamp'].min() if df_ml is not None else df['timestamp'].min()
    df_w = df[df['timestamp'] >= t_start]
    valid_w = valid[valid['timestamp'] >= t_start]

    # summary statistics
    rmse = np.sqrt((valid_w['error'] ** 2).mean())
    mae  = valid_w['error'].abs().mean()

    print(f"\nTotal samples: {len(df_w)}")
    print(f"\n--- LiDAR ---")
    print(f"Valid: {len(valid_w)} ({100.0 * len(valid_w) / len(df_w):.1f}%)")
    print(f"MAE: {mae:.4f} m")
    print(f"RMSE: {rmse:.4f} m")

    if df_cam_live is not None:
        cam_w = df_cam_live[df_cam_live['timestamp'] >= t_start]
        cam_valid = cam_w[cam_w['camera_headway_m'] >= 0]
        cam_error = cam_valid['camera_headway_m'] - cam_valid['gt_headway_m']
        print(f"\n--- Camera ---")
        print(f"Valid: {len(cam_valid)} ({100.0 * len(cam_valid) / len(cam_w):.1f}%)")
        print(f"MAE: {cam_error.abs().mean():.4f} m")
        print(f"RMSE: {np.sqrt((cam_error ** 2).mean()):.4f} m")

    if df_ml is not None:
        ml_error = df_ml['predicted_headway_m'] - df_ml['gt_headway_m']
        print(f"\n--- ML Fused ---")
        print(f"Predictions: {len(df_ml)}")
        print(f"MAE: {ml_error.abs().mean():.4f} m")
        print(f"RMSE: {np.sqrt((ml_error ** 2).mean()):.4f} m")
        print()

        # input columns only exist in logs recorded after they were added
        if 'lidar_in' in df_ml.columns:
            lid_miss = df_ml['lidar_in'] == -1.0
            cam_miss = df_ml['camera_in'] == -1.0
            print("Input missing (as the model saw it):")
            print(f"  LiDAR: {100.0 * lid_miss.mean():.1f}%")
            print(f"  Camera: {100.0 * cam_miss.mean():.1f}%")
            print(f"  Both: {100.0 * (lid_miss & cam_miss).mean():.1f}%")
            # one row per run, saved to a csv for all runs 
            err = ml_error.abs()
            outage = lid_miss & cam_miss
            gt = df_ml['gt_headway_m']
            summary = pd.DataFrame([{
                'run': DATETIME,
                'lidar_miss_%': 100.0 * lid_miss.mean(),
                'camera_miss_%': 100.0 * cam_miss.mean(),
                'both_miss_%': 100.0 * outage.mean(),
                # 'lidar_mae': (df_ml['lidar_in'] - gt)[~lid_miss].abs().mean(),
                # 'camera_mae': (df_ml['camera_in'] - gt)[~cam_miss].abs().mean(),
                # missing readings stay as -1, same as the offline table
                'lidar_mae': (df_ml['lidar_in'] - gt).abs().mean(),
                'camera_mae': (df_ml['camera_in'] - gt).abs().mean(),
                'ml_mae': err.mean(),
                'ml_rmse': (ml_error ** 2).mean() ** 0.5,
                'ml_mae_no_outage': err[~outage].mean(),
                # 'lidar_rmse': ((df_ml['lidar_in'] - gt)[~lid_miss] ** 2).mean() ** 0.5,
                'lidar_rmse': ((df_ml['lidar_in'] - gt) ** 2).mean() ** 0.5,
                'camera_rmse': ((df_ml['camera_in'] - gt) ** 2).mean() ** 0.5,
            }])
            summary_path = '../data/fault_runs_summary.csv'
            if os.path.exists(summary_path):
                old = pd.read_csv(summary_path)
                summary = pd.concat([old[old['run'] != DATETIME], summary])  # rerun replaces its own row
            summary.to_csv(summary_path, index=False)
            print(summary.round(3).to_string(index=False))

            # one-off check: ml vs the raw sensor it relies on, per input state
            cam_err = (df_ml['camera_in'] - gt).abs()
            lid_err = (df_ml['lidar_in'] - gt).abs()
            states = {
                'both valid': ~lid_miss & ~cam_miss,
                'lidar only': ~lid_miss & cam_miss,
                'camera only': lid_miss & ~cam_miss,
                'neither': lid_miss & cam_miss,
            }
            for name, m in states.items():
                if m.any():
                    print(f"{name}: {100 * m.mean():.1f}% of ticks, ml {err[m].mean():.3f} m, "
                        f"lidar {lid_err[m & ~lid_miss].mean():.3f} m, camera {cam_err[m & ~cam_miss].mean():.3f} m")
        else:
            print("Note: no lidar_in/camera_in columns in this log, so input dropout rates can't be computed")

    # save merged sensor data
    if df_cam is not None:

        # driven by every raw frame (df), not just camera's successful ones (df_cam)
        df_cam_for_merge = df_cam[['time', 'camera_corrected']].sort_values('time')
        merged_cam_lid_gt = pd.merge_asof(
            df.sort_values('time'),
            df_cam_for_merge,
            on='time', direction='nearest', tolerance=0.1
        )

        # missing readings become an explicit flag
        merged_cam_lid_gt['camera_valid'] = merged_cam_lid_gt['camera_corrected'].notna().astype(int)
        merged_cam_lid_gt['lidar_valid'] = (merged_cam_lid_gt['lidar_headway_m'] >= 0).astype(int)
        merged_cam_lid_gt['camera_corrected'] = merged_cam_lid_gt['camera_corrected'].fillna(-1.0)

        # ground truth for each row
        merged_cam_lid_gt = merged_cam_lid_gt[merged_cam_lid_gt['gt_headway_m'] >= 0]

        merged_out = merged_cam_lid_gt[['time', 'camera_corrected', 'camera_valid',
                                         'lidar_headway_m', 'lidar_valid', 'gt_headway_m']]

        merged_csv_path = os.path.join(run_dir, f'merged_cam_lid_gt{suffix}.csv')
        merged_out.to_csv(merged_csv_path, index=False)
        print(f"Saved merged sensor data for fusion: {merged_csv_path} "
              f"({len(merged_out)} time-aligned frames)")
    else:
        print("Skipping fusion export: df_cam is None (camera_calibrated CSV not found)")

    plot_headway(df, valid, df_cam_live, df_ml, output_dir)
    print(f"Saved: {output_dir}/headway_time_series_all.pdf and headway_time_series_zoom.pdf")
    # # headway time series

    # fig1, ax1 = plt.subplots(figsize=(10, 4))

    # ax1.plot(df['time'], df['gt_headway_m'].where(df['gt_headway_m'] >= 0), color='blue', linewidth=1.0, label=r'Ground Truth $d_{\mathrm{gt}}$')
    # ax1.plot(valid['time'], valid['lidar_headway_m'], color='red', linestyle='--',linewidth=1.0, alpha=1, label=r'LiDAR Estimate $\hat{d}$')
    # # time-sync cam data
    # if df_cam_live is not None:
    #     # -1.0 means no detection that tick, .where() leaves a gap
    #     ax1.plot(df_cam_live['time'], df_cam_live['camera_headway_m'].where(df_cam_live['camera_headway_m'] >= 0),
    #     color="#2ca02c", linewidth=0.8, alpha=0.6, linestyle='--', label=r'Camera Estimate')

    # # ml fused prediction, only fires when a fresh reading came from both sensors
    # if df_ml is not None:
    #     ax1.plot(df_ml['time'], df_ml['predicted_headway_m'],
    #       color='#e07a3e', linewidth=1.0, alpha=0.8,
    #       linestyle='--', label=r'ML Fused $\hat{d}_{\mathrm{ml}}$')

    # # gap_patch = mpatches.Patch(color='#ffcccc', alpha=0.7, label=r'Detection Lost')
    # # handles, labels = ax1.get_legend_handles_labels()
    # # ax1.legend(handles + [gap_patch], labels + [gap_patch.get_label()], loc='upper right', framealpha=0.9)
    # ax1.legend(loc='upper right', framealpha=0.9)

    # ax1.set_title(r'\textbf{Space Headway Over Time}')
    # ax1.set_xlabel(r'Time ($s$)')
    # ax1.set_ylabel(r'Space Headway ($m$)')
    # ax1.set_xlim(df['time'].min(), df['time'].max())
    # ax1.set_ylim(bottom=0)
    # ax1.grid(True, linestyle='--', alpha=0.6)

    # plot1_path = os.path.join(output_dir, 'headway_time_series_all.pdf')
    # fig1.savefig(plot1_path, format='pdf', bbox_inches='tight')
    # print(f"Saved: {plot1_path}")
    # plt.close(fig1)

    # plt.show()

# time window of the zoomed plot (s), tune after looking at the full plot
ZOOM = (99.0, 103.0)

COLORS = {'lidar': '#17707A', 'camera': '#C8651B', 'fused': '#8E1B6B'}


def draw_series(ax, df, valid, df_cam_live, df_ml):
    ax.plot(df['time'], df['gt_headway_m'].where(df['gt_headway_m'] >= 0),
            color='red', linestyle='--', linewidth=1.2, zorder=5, label='Ground truth')
    ax.plot(valid['time'], valid['lidar_headway_m'],
            color=COLORS['lidar'], linewidth=0.9, label='LiDAR')
    if df_cam_live is not None:
        # -1.0 means no detection that tick, .where() leaves a gap
        ax.plot(df_cam_live['time'], df_cam_live['camera_headway_m'].where(df_cam_live['camera_headway_m'] >= 0),
                color=COLORS['camera'], linewidth=0.9, alpha=0.8, label='Camera')
    if df_ml is not None:
        ax.plot(df_ml['time'], df_ml['predicted_headway_m'],
                color=COLORS['fused'], linewidth=0.9, label='Fused')
    ax.grid(True, color='0.88', linewidth=0.6)


def plot_headway(df, valid, df_cam_live, df_ml, output_dir):
    t0, t1 = ZOOM

    # full run, square
    fig1, ax1 = plt.subplots(figsize=(3.4, 3.4))
    draw_series(ax1, df, valid, df_cam_live, df_ml)
    ax1.axvspan(t0, t1, color='0.6', alpha=0.60, linewidth=0)  # marks the zoomed window
    ax1.legend(loc='upper right', framealpha=0.9)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Headway (m)')
    ax1.set_xlim(df['time'].min(), df['time'].max())
    ax1.set_ylim(bottom=0)
    fig1.savefig(os.path.join(output_dir, 'headway_time_series_all.pdf'), bbox_inches='tight')
    plt.close(fig1)

    # zoomed window, square
    fig2, ax2 = plt.subplots(figsize=(3.4, 3.4))
    draw_series(ax2, df, valid, df_cam_live, df_ml)
    ax2.legend(framealpha=0.9)
    ax2.set_xlim(t0, t1)
    # y limits from the lines inside the window only
    ys = np.concatenate([l.get_ydata(orig=False)[(l.get_xdata(orig=False) >= t0) & (l.get_xdata(orig=False) <= t1)]
                         for l in ax2.get_lines()])
    pad = 0.05 * (np.nanmax(ys) - np.nanmin(ys))
    ax2.set_ylim(np.nanmin(ys) - pad, np.nanmax(ys) + pad)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Headway (m)')
    fig2.savefig(os.path.join(output_dir, 'headway_time_series_zoom.pdf'), bbox_inches='tight')
    plt.close(fig2)

if __name__ == '__main__':
    main()
