from drivers.gps.provider import GPSProvider
from drivers.motor.hbridge import DualHBridgeMotorDriver
from drivers.sensors.ultrasonic_array import DualUltrasonicArray
from drivers.camera.picam2 import PiCam2FrameDriver
from drivers.sensors.mpu9150 import MPU9150


class RoverAPI:
    def __init__(
        self,
        gps_port="/dev/ttyAMA0",
        gps_baud=9600,
        gps_fallback_file="/home/yasen/gps_fallback.env",
        left_motor_pins=(20, 21),
        right_motor_pins=(16, 12),
        motor_pwm_pins=(19, 13),
        motor_pwm_frequency_hz=100,
        ultrasonic1_pins=(23, 24),
        ultrasonic2_pins=(27, 17),
        ultrasonic3_pins=(5, 6),
        imu_bus=1,
        imu_address=0x68,
    ):
        self.gps = GPSProvider(port=gps_port, baud=gps_baud, fallback_file=gps_fallback_file)
        self.ultrasonic = DualUltrasonicArray(
            sensor1_trig=ultrasonic1_pins[0],
            sensor1_echo=ultrasonic1_pins[1],
            sensor2_trig=ultrasonic2_pins[0],
            sensor2_echo=ultrasonic2_pins[1],
            sensor3_trig=ultrasonic3_pins[0],
            sensor3_echo=ultrasonic3_pins[1],
        )
        self.motor = DualHBridgeMotorDriver(
            left_in1=left_motor_pins[0],
            left_in2=left_motor_pins[1],
            right_in1=right_motor_pins[0],
            right_in2=right_motor_pins[1],
            left_pwm_pin=motor_pwm_pins[0],
            right_pwm_pin=motor_pwm_pins[1],
            pwm_frequency_hz=motor_pwm_frequency_hz,
        )
        self.camera = PiCam2FrameDriver()
        self.imu = MPU9150(bus=imu_bus, address=imu_address)

    def get_gps_values(self, timeout_seconds=2.0, allow_fallback=True):
        return self.gps.get_position(timeout_seconds=timeout_seconds, allow_fallback=allow_fallback)

    def get_gsm_values(self, timeout_seconds=2.0, allow_fallback=True):
        return self.get_gps_values(timeout_seconds=timeout_seconds, allow_fallback=allow_fallback)

    def get_ultrasonic(self, sensor_id=None, timeout_seconds=0.015):
        if sensor_id is None:
            return self.ultrasonic.read_all(timeout_seconds=timeout_seconds)
        return self.ultrasonic.read_sensor(sensor_id=sensor_id, timeout_seconds=timeout_seconds)

    def set_motor(self, side, direction, speed=100):
        return self.motor.set_motor(side=side, direction=direction, speed=speed)

    def drive(self, left_direction, right_direction, left_speed=100, right_speed=100):
        return self.motor.drive(
            left_direction=left_direction,
            right_direction=right_direction,
            left_speed=left_speed,
            right_speed=right_speed,
        )

    def set_motor_speed(self, side, speed):
        return self.motor.set_speed(side=side, speed=speed)

    def set_motor_speeds(self, left_speed, right_speed):
        return self.motor.set_speeds(left_speed=left_speed, right_speed=right_speed)

    def stop_motors(self):
        self.motor.stop()

    def getframe(self):
        return self.camera.take_picture()

    def take_picture(self):
        return self.getframe()

    def get_camera_frame(self):
        return self.getframe()

    def get_imu(self):
        return self.imu.read_all()

    def get_accel(self):
        return self.imu.read_accel()

    def get_gyro(self):
        return self.imu.read_gyro()

    def get_temperature(self):
        return self.imu.read_temperature()

    def get_mag(self):
        return self.imu.read_mag()

    def get_orientation(self):
        return self.imu.read_orientation()

    def close(self):
        self.gps.close()
        self.motor.cleanup()
        self.ultrasonic.cleanup()
        self.camera.close()
        self.imu.close()
