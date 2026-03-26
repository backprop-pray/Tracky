#!/usr/bin/env python3
import argparse
import os
import sys
import time

from drivers.gps.nmea import extract_sentences, parse_lat_lon
from drivers.gps.uart import UartReader


def get_fallback_coords():
    lat_raw = os.getenv('GPS_FALLBACK_LAT')
    lon_raw = os.getenv('GPS_FALLBACK_LON')
    if not lat_raw or not lon_raw:
        return None

    try:
        return float(lat_raw), float(lon_raw)
    except ValueError:
        return None


def print_fallback(coords):
    lat, lon = coords
    print(f'{lat:.6f},{lon:.6f} (FALLBACK)')
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description='Read GPS UART and print latitude/longitude')
    parser.add_argument('--port', default='/dev/ttyAMA0', help='UART device path')
    parser.add_argument('--baud', type=int, default=9600, help='UART baud rate')
    parser.add_argument('--status-interval', type=float, default=5.0, help='Seconds between status output')
    args = parser.parse_args()

    fallback = get_fallback_coords()
    reader = UartReader(port=args.port, baud=args.baud)

    try:
        reader.open()
    except OSError as exc:
        print(f'Failed to open {args.port}: {exc}', file=sys.stderr)
        if fallback is not None:
            print_fallback(fallback)
        else:
            print('NO_FIX')
            sys.stdout.flush()
        return 1

    print(
        f'Reading GPS on {args.port} at {args.baud} baud. Waiting for fix...',
        file=sys.stderr,
    )

    last_status = 0.0

    try:
        for line in reader.iter_lines():
            got_fix = False
            for sentence in extract_sentences(line):
                latlon = parse_lat_lon(sentence)
                if latlon is None:
                    continue
                lat, lon = latlon
                print(f'{lat:.6f},{lon:.6f}')
                sys.stdout.flush()
                got_fix = True

            now = time.monotonic()
            if not got_fix and now - last_status >= args.status_interval:
                if fallback is not None:
                    print('No GPS fix yet. Using configured fallback coordinates.', file=sys.stderr)
                    print_fallback(fallback)
                else:
                    print('No GPS fix yet.', file=sys.stderr)
                    print('NO_FIX')
                    sys.stdout.flush()
                last_status = now
    except KeyboardInterrupt:
        print('Stopped.', file=sys.stderr)
        return 0
    finally:
        reader.close()


if __name__ == '__main__':
    raise SystemExit(main())
