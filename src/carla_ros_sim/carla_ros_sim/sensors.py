import carla

class SensorManager:
    def __init__(self, world, ego_vehicle):
        self.world = world
        self.ego_vehicle = ego_vehicle
        self.blueprint_library = world.get_blueprint_library()
        self.spawned_sensors = []

    def attach_all(self):
        """spawns and attaches IMU, GNSS, Camera, and LiDAR."""
        # car blueprint
        imu_bp = self.blueprint_library.find('sensor.other.imu')
        imu_bp.set_attribute('role_name', 'imu_sensor')
        
        gnss_bp = self.blueprint_library.find('sensor.other.gnss')
        gnss_bp.set_attribute('role_name', 'gnss_sensor')

        camera_bp = self.blueprint_library.find('sensor.camera.rgb')
        camera_bp.set_attribute('role_name', 'front_camera')
        camera_bp.set_attribute('image_size_x', '800')
        camera_bp.set_attribute('image_size_y', '600')
        camera_bp.set_attribute('fov', '90.0')

        lidar_bp = self.blueprint_library.find('sensor.lidar.ray_cast')
        lidar_bp.set_attribute('role_name', 'top_lidar')
        lidar_bp.set_attribute('channels', '32')
        lidar_bp.set_attribute('range', '80.0')
        lidar_bp.set_attribute('points_per_second', '600000')
        lidar_bp.set_attribute('rotation_frequency', '10.0')
        lidar_bp.set_attribute('upper_fov', '2.0')
        lidar_bp.set_attribute('lower_fov', '-25.0')

        # transform
        center_transform = carla.Transform()
        camera_transform = carla.Transform(carla.Location(x=1.5, z=1.2))
        lidar_transform = carla.Transform(carla.Location(x=0.0, z=2.5))

        # sensor attachment
        imu = self.world.spawn_actor(imu_bp, center_transform, attach_to=self.ego_vehicle)
        gnss = self.world.spawn_actor(gnss_bp, center_transform, attach_to=self.ego_vehicle)
        camera = self.world.spawn_actor(camera_bp, camera_transform, attach_to=self.ego_vehicle)
        lidar = self.world.spawn_actor(lidar_bp, lidar_transform, attach_to=self.ego_vehicle)

        self.spawned_sensors.extend([imu, gnss, camera, lidar])

    def cleanup(self):
        """stops and destroys all sensors."""
        for sensor in self.spawned_sensors:
            if sensor.is_alive:
                if hasattr(sensor, 'stop'):
                    sensor.stop()
                sensor.destroy()

