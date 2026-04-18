#!/usr/bin/env python3
import sys
import time
import math
sys.path.insert(0, "/home/yasen/patatnik/embedded")

from drivers.motor.hbridge import DualHBridgeMotorDriver
from drivers.sensors.mpu9150 import MPU9150

MOTOR_SPEED   = 100
MOTOR_RUN_TIME = 2.0
CALIB_TIME    = 2.0
SAMPLE_DT     = 0.02   # 50 Hz
G             = 9.81   # m/s²


def calibrate(imu):
    print(f"Calibrating {CALIB_TIME}s — keep robot still ...")
    samples = []
    end = time.monotonic() + CALIB_TIME
    while time.monotonic() < end:
        samples.append(imu.read_accel())
        time.sleep(SAMPLE_DT)
    bx = sum(s[0] for s in samples) / len(samples)
    by = sum(s[1] for s in samples) / len(samples)
    print(f"Bias  x={bx:+.5f}g  y={by:+.5f}g  ({len(samples)} samples)")
    return bx, by


def main():
    imu    = MPU9150(bus=1, address=0x68)
    driver = DualHBridgeMotorDriver()

    try:
        bx, by = calibrate(imu)

        vx = vy = 0.0
        px = py = 0.0
        prev_t = time.monotonic()

        print(f"\nDriving {MOTOR_SPEED}% forward for {MOTOR_RUN_TIME}s ...")
        driver.set_both_forward(speed=MOTOR_SPEED)

        deadline = time.monotonic() + MOTOR_RUN_TIME
        while time.monotonic() < deadline:
            ax_g, ay_g, _ = imu.read_accel()
            now = time.monotonic()
            dt  = now - prev_t
            prev_t = now

            ax = (ax_g - bx) * G
            ay = (ay_g - by) * G

            vx += ax * dt
            vy += ay * dt
            px += vx * dt
            py += vy * dt

            time.sleep(SAMPLE_DT)

        driver.stop()
        print("Motors stopped.\n")

        dist = math.sqrt(px**2 + py**2)
        print(f"Estimated distance : {dist:.3f} m")
        print(f"  x={px:+.3f} m   y={py:+.3f} m")

    finally:
        driver.cleanup()
        imu.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
