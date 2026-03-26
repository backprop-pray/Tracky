#!/usr/bin/env python3
import argparse
import sys

from drivers.gps.uart import UartReader


def main():
    parser = argparse.ArgumentParser(description='Minicom-like raw UART reader')
    parser.add_argument('--port', default='/dev/ttyAMA0', help='UART device path')
    parser.add_argument('--baud', type=int, default=9600, help='UART baud rate')
    args = parser.parse_args()

    reader = UartReader(port=args.port, baud=args.baud)

    try:
        reader.open()
    except OSError as exc:
        print(f'Failed to open {args.port}: {exc}', file=sys.stderr)
        return 1

    print(
        f'Reading raw UART from {args.port} at {args.baud} baud (minicom style). Ctrl+C to stop.',
        file=sys.stderr,
    )

    try:
        while True:
            data = reader.read(1024)
            if data:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
    except KeyboardInterrupt:
        print('Stopped.', file=sys.stderr)
        return 0
    finally:
        reader.close()


if __name__ == '__main__':
    raise SystemExit(main())
