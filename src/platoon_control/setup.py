from setuptools import find_packages, setup

package_name = 'platoon_control'

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
    description='platoon scenario and closed loop follower control',
    license='TODO: License declaration',
    entry_points={
        'console_scripts': [],
    },
)
