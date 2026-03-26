#!/usr/bin/env python3
import argparse
import time

from drivers.motor.hbridge import DualHBridgeMotorDriver


def main():
    parser = argparse.ArgumentParser(description='Run both motors forward then reverse')
    parser.add_argument('--step-seconds', type=float, default=2.0)
    parser.add_argument('--m1-in1', type=int, default=20)
    parser.add_argument('--m1-in2', type=int, default=21)
    parser.add_argument('--m2-in1', type=int, default=16)
    parser.add_argument('--m2-in2', type=int, default=12)
    args = parser.parse_args()

    driver = DualHBridgeMotorDriver(
        m1_in1=args.m1_in1,
        m1_in2=args.m1_in2,
        m2_in1=args.m2_in1,
        m2_in2=args.m2_in2,
    )

    try:
        driver.set_both_forward()
        print(
            f'Both forward: M1({args.m1_in1}=H, {args.m1_in2}=L) '
            f'M2({args.m2_in1}=H, {args.m2_in2}=L)'
        )
        time.sleep(args.step_seconds)

        driver.set_both_reverse()
        print(
            f'Both reverse: M1({args.m1_in1}=L, {args.m1_in2}=H) '
            f'M2({args.m2_in1}=L, {args.m2_in2}=H)'
        )
        time.sleep(args.step_seconds)
    finally:
        driver.cleanup()
        print('Done. All pins set LOW and cleaned up.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
