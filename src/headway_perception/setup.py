from setuptools import find_packages, setup

package_name = 'headway_perception'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ruby',
    maintainer_email='ms0393@uah.edu',
    description='lidar, camera and ml fused headway estimators, plus sensor fault injector',
    license='TODO: License declaration',
    entry_points={
        'console_scripts': [
            'lidar_headway_estimator = headway_perception.lidar_headway_estimator:main',
            'camera_headway_estimator = headway_perception.camera_headway_estimator:main',
            'ml_headway_estimator = headway_perception.ml_headway_estimator:main',
            'fault_injector = headway_perception.fault_injector:main',
        ],
    },
)
