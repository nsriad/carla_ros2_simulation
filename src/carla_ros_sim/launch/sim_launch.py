from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, ExecuteProcess, RegisterEventHandler, EmitEvent
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.parameter_descriptions import ParameterValue
import datetime

def generate_launch_description():
    record_arg = DeclareLaunchArgument('record', default_value='false')
    duration_arg = DeclareLaunchArgument('duration', default_value='60')
    custom_map_arg = DeclareLaunchArgument('use_custom_map', default_value='false')
    model_dir_arg = DeclareLaunchArgument(
        'model_dir', default_value='data/multimodal_dataset_20260713_191320/processed_fusion_clean')
    dropout_lidar_arg = DeclareLaunchArgument('dropout_lidar', default_value='0.0')
    dropout_camera_arg = DeclareLaunchArgument('dropout_camera', default_value='0.0')

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
             '/carla/tesla_ego/camera_headway',
             '-o', bag_name,
             '--use-sim-time'],
        output='screen'
    )

    vehicle_spawner_node = Node(
        package='carla_ros_sim',
        executable='vehicle_spawner',
        name='vehicle_spawner',
        parameters=[{
            'duration': ParameterValue(LaunchConfiguration('duration'), value_type=int),
            'use_custom_map': ParameterValue(LaunchConfiguration('use_custom_map'), value_type=bool),
        }],
        output='screen'
    )

    return LaunchDescription([
        record_arg,
        duration_arg,
        custom_map_arg,
        model_dir_arg,
        dropout_lidar_arg,
        dropout_camera_arg,
        bag_recorder,
        vehicle_spawner_node,
        RegisterEventHandler(
            OnProcessExit(
                target_action=vehicle_spawner_node,
                on_exit=[EmitEvent(event=Shutdown(reason='vehicle_spawner finished'))]
            )
        ),
        Node(
            package='headway_perception',
            executable='lidar_headway_estimator',
            name='lidar_headway_estimator',
            parameters=[{
                'use_sim_time': True,
                'session_id': timestamp
            }],
            output='screen'
        ),
        Node(
            package='headway_perception',
            executable='camera_headway_estimator',
            name='camera_headway_estimator',
            parameters=[{
                'use_sim_time': True,
                'session_id': timestamp
            }],
            output='screen'
        ),
        Node(
            package='headway_perception',
            executable='ml_headway_estimator',
            name='ml_headway_estimator',
            parameters=[{
                'use_sim_time': True,
                'session_id': timestamp,
                'model_dir': LaunchConfiguration('model_dir'),
            }],
            output='screen'
        ),
        Node(
            package='headway_perception',
            executable='fault_injector',
            name='fault_injector',
            parameters=[{
                'use_sim_time': True,
                'dropout_lidar': ParameterValue(LaunchConfiguration('dropout_lidar'), value_type=float),
                'dropout_camera': ParameterValue(LaunchConfiguration('dropout_camera'), value_type=float),
            }],
            output='screen'
        ),
    ])