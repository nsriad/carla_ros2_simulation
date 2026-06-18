import carla
import math

class PIDController:
    def __init__(self, target_gap=5.0, kp=0.3, ki=0.01, kd=0.6):
        self.target_gap = target_gap
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.prev_error = 0.0
        self.integral = 0.0

    def get_control(self, current_gap, dt=0.1):
        error = current_gap - self.target_gap
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        self.prev_error = error

        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)

        control = carla.VehicleControl()
        if output > 0:
            control.throttle = min(output, 1.0)
            control.brake = 0.0
        else:
            control.throttle = 0.0
            control.brake = min(abs(output), 1.0)
        return control

class StopAndGoLeader:
    def __init__(self):
        self.is_going = True

    def toggle(self):
        self.is_going = not self.is_going
        return "ACCELERATING" if self.is_going else "BRAKING"

    def get_control(self):
        control = carla.VehicleControl()
        if self.is_going:
            control.throttle = 0.5
            control.brake = 0.0
        else:
            control.throttle = 0.0
            control.brake = 0.6
        return control
