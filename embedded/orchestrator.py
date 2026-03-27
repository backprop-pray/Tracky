#!/usr/bin/env python3
import argparse
import base64
import json
import logging
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from drivers.gps.provider import GPSProvider

try:
    import cv2
except Exception:
    cv2 = None


class LatestFrameBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._timestamp = 0.0

    def update(self, frame):
        with self._lock:
            self._frame = frame.copy()
            self._timestamp = time.time()

    def get(self):
        with self._lock:
            if self._frame is None:
                return None, 0.0
            return self._frame.copy(), self._timestamp


class OptionalUSBStreamClient:
    def __init__(self, laptop_ip, port, endpoint):
        self.laptop_ip = laptop_ip
        self.port = port
        self.endpoint = endpoint

    @property
    def enabled(self):
        return bool(self.laptop_ip)

    def send_frame(self, frame, timestamp):
        if not self.enabled:
            return
        # Placeholder for future USB frame streaming transport to laptop.
        # Keep this optional so rover control never crashes if streaming fails.
        _ = frame, timestamp


class AnomalyReporter:
    def __init__(self, laptop_ip, port, endpoint, timeout_seconds=2.0):
        self.laptop_ip = laptop_ip
        self.port = port
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self):
        return bool(self.laptop_ip)

    @property
    def url(self):
        return f'http://{self.laptop_ip}:{self.port}{self.endpoint}'

    def send(self, frame, gps_data, ai_result):
        if not self.enabled:
            logging.info('Anomaly detected but laptop IP is not set, skipping send.')
            return
        if cv2 is None:
            logging.warning('cv2 not available, cannot encode anomaly image.')
            return

        try:
            ok, encoded = cv2.imencode('.jpg', frame)
            if not ok:
                logging.warning('Could not encode anomaly frame as JPEG.')
                return

            payload = {
                'timestamp': time.time(),
                'gps': gps_data,
                'ai_result': ai_result,
                'image_jpeg_b64': base64.b64encode(encoded.tobytes()).decode('ascii'),
            }
            body = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.url,
                data=body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                response.read(32)
            logging.info('Anomaly report sent to %s', self.url)
        except urllib.error.URLError as exc:
            logging.warning('Could not send anomaly report: %s', exc)
        except Exception as exc:
            logging.warning('Unexpected anomaly send error: %s', exc)


def parse_args():
    parser = argparse.ArgumentParser(description='Orchestrator for PPO rover + optional USB AI monitor.')
    parser.add_argument('--ppo-script', default='ppo_rover.py', help='Path to ppo_rover.py')
    parser.add_argument('--disable-usb', action='store_true', help='Disable optional USB capture pipeline.')
    parser.add_argument('--usb-device', default=None, help='USB camera device path or index, e.g. /dev/video8 or 1')
    parser.add_argument('--usb-width', type=int, default=1280)
    parser.add_argument('--usb-height', type=int, default=720)
    parser.add_argument('--usb-fps', type=int, default=30)
    parser.add_argument('--ai-interval', type=float, default=0.5, help='Seconds between AI pipeline runs.')
    parser.add_argument('--anomaly-cooldown', type=float, default=5.0, help='Min seconds between anomaly sends.')
    parser.add_argument('--gps-port', default='/dev/ttyAMA0')
    parser.add_argument('--gps-baud', type=int, default=9600)
    parser.add_argument('--gps-fallback-file', default='/home/yasen/gps_fallback.env')
    parser.add_argument('--laptop-ip', default=None, help='Optional laptop IP for stream/report sending.')
    parser.add_argument('--laptop-port', type=int, default=8080)
    parser.add_argument('--stream-endpoint', default='/stream/frame')
    parser.add_argument('--anomaly-endpoint', default='/anomaly/report')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    return parser.parse_args()


def build_usb_candidates(explicit_device):
    if explicit_device is not None:
        if str(explicit_device).isdigit():
            return [int(explicit_device)]
        return [str(explicit_device)]

    candidates = []
    by_id = Path('/dev/v4l/by-id')
    if by_id.exists():
        for dev in sorted(by_id.glob('usb-*-video-index0')):
            candidates.append(str(dev))
        for dev in sorted(by_id.glob('usb-*-video-index2')):
            candidates.append(str(dev))

    for dev in ('/dev/video8', '/dev/video10', '/dev/video0', '/dev/video2'):
        if Path(dev).exists():
            candidates.append(dev)

    unique = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def try_open_camera(source, width, height, fps):
    if cv2 is None:
        return None

    cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        cap.release()
        return None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    for _ in range(5):
        ok, _ = cap.read()
        if ok:
            return cap

    cap.release()
    return None


def open_usb_camera(explicit_device, width, height, fps):
    candidates = build_usb_candidates(explicit_device)
    if not candidates:
        raise RuntimeError('No USB camera candidates found.')

    for source in candidates:
        cap = try_open_camera(source, width, height, fps)
        if cap is not None:
            return cap, source

    raise RuntimeError(f'Could not open any USB camera candidate: {candidates}')


def run_ai_pipeline(frame):
    # Placeholder AI pipeline. Replace with real disease/anomaly inference.
    _ = frame
    return {
        'is_sick': False,
        'is_anomaly': False,
        'label': None,
        'score': 0.0,
    }


def read_gps_snapshot(gps_provider):
    try:
        return gps_provider.get_position(timeout_seconds=2.0, allow_fallback=True)
    except Exception as exc:
        logging.warning('GPS read failed: %s', exc)
        return {'lat': None, 'lon': None, 'source': 'error', 'fix': False}


def usb_capture_loop(stop_event, frame_buffer, stream_client, usb_device, usb_width, usb_height, usb_fps):
    if cv2 is None:
        logging.warning('cv2 import failed, USB capture disabled.')
        return

    try:
        cap, source = open_usb_camera(usb_device, usb_width, usb_height, usb_fps)
        logging.info('USB camera opened from %s', source)
    except Exception as exc:
        logging.warning('Optional USB camera stream unavailable: %s', exc)
        return

    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.02)
                continue

            frame_buffer.update(frame)

            try:
                stream_client.send_frame(frame, time.time())
            except Exception as exc:
                logging.warning('Optional USB stream send failed: %s', exc)
    finally:
        cap.release()
        logging.info('USB capture loop stopped.')


def ai_monitor_loop(stop_event, frame_buffer, gps_provider, anomaly_reporter, ai_interval, anomaly_cooldown):
    last_report_ts = 0.0

    try:
        while not stop_event.is_set():
            frame, _ts = frame_buffer.get()
            if frame is None:
                time.sleep(ai_interval)
                continue

            try:
                result = run_ai_pipeline(frame)
            except Exception as exc:
                logging.warning('AI pipeline failed: %s', exc)
                time.sleep(ai_interval)
                continue

            is_flagged = bool(result.get('is_sick') or result.get('is_anomaly'))
            now = time.monotonic()
            if is_flagged and (now - last_report_ts >= anomaly_cooldown):
                gps = read_gps_snapshot(gps_provider)
                anomaly_reporter.send(frame=frame, gps_data=gps, ai_result=result)
                last_report_ts = now

            time.sleep(ai_interval)
    finally:
        gps_provider.close()
        logging.info('AI monitor loop stopped.')


def start_ppo_process(ppo_script_path):
    ppo_script = Path(ppo_script_path)
    if not ppo_script.is_absolute():
        ppo_script = (Path(__file__).resolve().parent / ppo_script).resolve()

    if not ppo_script.exists():
        raise FileNotFoundError(f'PPO script not found: {ppo_script}')

    logging.info('Starting PPO rover from %s', ppo_script)
    return subprocess.Popen([sys.executable, str(ppo_script)], cwd=str(ppo_script.parent))


def stop_ppo_process(process):
    if process.poll() is not None:
        return

    try:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=8)
        return
    except Exception:
        pass

    try:
        process.terminate()
        process.wait(timeout=5)
        return
    except Exception:
        pass

    process.kill()


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    stop_event = threading.Event()
    frame_buffer = LatestFrameBuffer()
    stream_client = OptionalUSBStreamClient(args.laptop_ip, args.laptop_port, args.stream_endpoint)
    anomaly_reporter = AnomalyReporter(args.laptop_ip, args.laptop_port, args.anomaly_endpoint)

    gps_provider = GPSProvider(
        port=args.gps_port,
        baud=args.gps_baud,
        fallback_file=args.gps_fallback_file,
    )

    ppo_process = start_ppo_process(args.ppo_script)

    usb_thread = None
    if args.disable_usb:
        logging.info('USB pipeline disabled by flag.')
    else:
        usb_thread = threading.Thread(
            target=usb_capture_loop,
            args=(
                stop_event,
                frame_buffer,
                stream_client,
                args.usb_device,
                args.usb_width,
                args.usb_height,
                args.usb_fps,
            ),
            daemon=True,
            name='usb-capture',
        )
        usb_thread.start()

    ai_thread = threading.Thread(
        target=ai_monitor_loop,
        args=(
            stop_event,
            frame_buffer,
            gps_provider,
            anomaly_reporter,
            args.ai_interval,
            args.anomaly_cooldown,
        ),
        daemon=True,
        name='ai-monitor',
    )
    ai_thread.start()

    return_code = 0
    try:
        while True:
            rc = ppo_process.poll()
            if rc is not None:
                return_code = rc
                logging.info('PPO rover exited with code %s', rc)
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info('Keyboard interrupt received, shutting down orchestrator.')
    finally:
        stop_event.set()

        if usb_thread is not None:
            usb_thread.join(timeout=2.0)
        ai_thread.join(timeout=2.0)

        stop_ppo_process(ppo_process)

    return return_code


if __name__ == '__main__':
    raise SystemExit(main())
