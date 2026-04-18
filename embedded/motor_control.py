#!/usr/bin/env python3
import time

from drivers.motor.hbridge import DualHBridgeMotorDriver

M1_IN1 = 20
M1_IN2 = 21
M2_IN1 = 16
M2_IN2 = 13
M1_PWM = 18
M2_PWM = 19
PWM_FREQ_HZ = 100
STEP_SECONDS = 2.0


def main():
    driver = DualHBridgeMotorDriver(
        m1_in1=M1_IN1,
        m1_in2=M1_IN2,
        m2_in1=M2_IN1,
        m2_in2=M2_IN2,
        m1_pwm=M1_PWM,
        m2_pwm=M2_PWM,
        pwm_frequency_hz=PWM_FREQ_HZ,
        right_speed_factor=0.9,
    )

    try:
        driver.set_both_forward(speed=70)
        print(
            f'Both forward @70%: M1 dir({M1_IN1},{M1_IN2}) pwm({M1_PWM}) '
            f'M2 dir({M2_IN1},{M2_IN2}) pwm({M2_PWM})'
        )
        time.sleep(STEP_SECONDS)

        driver.set_both_reverse(speed=70)
        print('Both reverse @70%')
        time.sleep(STEP_SECONDS)
    finally:
        driver.cleanup()
        print('Done. All pins set LOW and cleaned up.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
