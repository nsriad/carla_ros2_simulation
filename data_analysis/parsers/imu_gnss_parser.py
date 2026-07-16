#!/usr/bin/env python3
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

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
    # define paths
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv} <dataset_name>")
        sys.exit(1)
    bag_dir = '../data/' + sys.argv[1]

    # output directly inside the run's folder
    out_dir = os.path.join(bag_dir, 'processed_imu_gnss')

    # create output directories
    os.makedirs(out_dir, exist_ok=True)
    
    typestore = get_typestore(Stores.ROS2_HUMBLE)
    imu_data, gnss_data = [], []

    print(f"Extracting imu gnss sensor data from: {bag_dir}")
    
    with Reader(bag_dir) as reader:
        for connection, timestamp, rawdata in reader.messages():
            # Skip messages that aren't IMU or GNSS
            if connection.topic not in ['/carla/tesla_ego/imu_sensor', '/carla/tesla_ego/gnss_sensor']:
                continue
                
            msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
            time_sec = timestamp / 1e9

            if connection.topic == '/carla/tesla_ego/imu_sensor':
                imu_data.append({
                    'time': time_sec,
                    'accel_x': msg.linear_acceleration.x,
                    'accel_y': msg.linear_acceleration.y,
                    'accel_z': msg.linear_acceleration.z,
                    'gyro_x': msg.angular_velocity.x,
                    'gyro_y': msg.angular_velocity.y,
                    'gyro_z': msg.angular_velocity.z
                })
            elif connection.topic == '/carla/tesla_ego/gnss_sensor':
                gnss_data.append({
                    'time': time_sec,
                    'lat': msg.latitude,
                    'lon': msg.longitude,
                    'alt': msg.altitude
                })

    # convert to DataFrames
    df_imu = pd.DataFrame(imu_data)
    df_gnss = pd.DataFrame(gnss_data)

    # normalize time so the graphs start exactly at t=0
    t0 = min(df_imu['time'].min(), df_gnss['time'].min())
    df_imu['time'] -= t0
    df_gnss['time'] -= t0

    # saving data to CSV for future reference
    imu_csv = os.path.join(out_dir, 'imu_data.csv')
    gnss_csv = os.path.join(out_dir, 'gnss_data.csv')
    df_imu.to_csv(imu_csv, index=False)
    df_gnss.to_csv(gnss_csv, index=False)
    
    print(f"Saved {len(df_imu)} IMU records to {imu_csv}")
    print(f"Saved {len(df_gnss)} GNSS records to {gnss_csv}")

    # generate plot
    print("Generating plot...")
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # plot X and Y acceleration (using a deep purple for the primary forward axis)
    ax.plot(df_imu['time'], df_imu['accel_x'], label=r'Forward Accel ($a_x$)', color='#663399', linewidth=1.5)
    ax.plot(df_imu['time'], df_imu['accel_y'], label=r'Lateral Accel ($a_y$)', color='#2e8b57', linewidth=1.5, alpha=0.8)
    
    ax.set_title(r'\textbf{Ego Vehicle Linear Acceleration Over Time}')
    ax.set_xlabel(r'Time ($s$)')
    ax.set_ylabel(r'Acceleration ($m/s^2$)')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6)

    # save as pdf
    plot_path = os.path.join(out_dir, 'acceleration_plot.pdf')
    plt.savefig(plot_path, format='pdf', bbox_inches='tight')
    print(f"Plot saved to {plot_path}")
    
    # plt.show()

if __name__ == '__main__':
    main()
