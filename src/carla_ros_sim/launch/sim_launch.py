from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
import datetime

def generate_launch_description():
    # toggle recording with: ros2 launch carla_ros_sim sim_launch.py record:=true
    record_arg = DeclareLaunchArgument('record', default_value='false')
    duration_arg = DeclareLaunchArgument('duration', default_value='60')  # seconds

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bag_name  = f'data/multimodal_dataset_{timestamp}'

    bag_recorder = ExecuteProcess(
        condition=IfCondition(LaunchConfiguration('record')),
        cmd=['ros2', 'bag', 'record',
             '/carla/tesla_ego/top_lidar_roi',
             '/carla/tesla_ego/imu_sensor',
             '/carla/tesla_ego/gnss_sensor',
             '/carla/tesla_ego/front_camera/image',
             '/carla/tesla_ego/ground_truth_headway',
             '-o', bag_name],
        output='screen'
    )

    return LaunchDescription([
        record_arg,
        bag_recorder,
        duration_arg,
        Node(
            package='carla_ros_sim',
            executable='vehicle_spawner',
            name='vehicle_spawner',
            parameters=[{
                'duration': LaunchConfiguration('duration')
            }],
            output='screen'
        ),
        Node(
            package='carla_ros_sim',
            executable='lidar_headway_estimator',
            name='lidar_headway_estimator',
            output='screen'
        )
    ])