#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path

import cv2

WINDOW_NAME = 'USB Camera Stream'
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30
AUTO_FPS_FRAMES = 60


def process_frame(frame):
    return frame


def parse_args():
    parser = argparse.ArgumentParser(description='OpenCV stream from USB camera.')
    parser.add_argument(
        '--device',
        default=None,
        help='Video device path or camera index (for example /dev/video8 or 1).',
    )
    parser.add_argument('--width', type=int, default=DEFAULT_WIDTH)
    parser.add_argument('--height', type=int, default=DEFAULT_HEIGHT)
    parser.add_argument('--fps', type=int, default=DEFAULT_FPS, help='Requested camera capture FPS.')
    parser.add_argument(
        '--output-fps',
        type=float,
        default=0.0,
        help='Output video FPS. 0 = auto-detect from measured capture rate.',
    )
    parser.add_argument(
        '--no-gui',
        action='store_true',
        help='Disable window preview and run headless.',
    )
    parser.add_argument(
        '--max-frames',
        type=int,
        default=0,
        help='Stop after N frames (0 means unlimited).',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Optional output video path (for example out.mp4).',
    )
    return parser.parse_args()


def has_display():
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


def _build_candidates(explicit_device):
    if explicit_device is not None:
        if explicit_device.isdigit():
            return [int(explicit_device)]
        return [explicit_device]

    candidates = []

    by_id_dir = Path('/dev/v4l/by-id')
    if by_id_dir.exists():
        for p in sorted(by_id_dir.glob('usb-*-video-index0')):
            candidates.append(str(p))
        for p in sorted(by_id_dir.glob('usb-*-video-index2')):
            candidates.append(str(p))

    for dev in ('/dev/video8', '/dev/video10', '/dev/video0', '/dev/video2', '/dev/video1'):
        if Path(dev).exists():
            candidates.append(dev)

    unique = []
    seen = set()
    for c in candidates:
        if c not in seen:
            unique.append(c)
            seen.add(c)
    return unique


def _try_open(source, width, height, fps):
    camera = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(source)
    if not camera.isOpened():
        camera.release()
        return None

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    camera.set(cv2.CAP_PROP_FPS, fps)

    for _ in range(5):
        ok, _frame = camera.read()
        if ok:
            return camera

    camera.release()
    return None


def open_camera(explicit_device, width, height, fps):
    candidates = _build_candidates(explicit_device)
    if not candidates:
        raise RuntimeError('No camera candidates found under /dev/video* or /dev/v4l/by-id.')

    for source in candidates:
        camera = _try_open(source, width, height, fps)
        if camera is not None:
            return camera, source

    raise RuntimeError(f'Could not open any camera candidate: {candidates}')


def create_writer(output_path, frame_width, frame_height, fps):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), (int(frame_width), int(frame_height)))
    if not writer.isOpened():
        raise RuntimeError(f'Could not open output file for writing: {output_path}')
    return writer


def clamp_fps(value):
    return max(1.0, min(120.0, float(value)))


def init_writer_if_ready(args, output_frames, output_start_ts, writer, processed):
    if not args.output:
        return writer, output_start_ts, False
    if writer is not None:
        return writer, output_start_ts, False

    output_frames.append(processed.copy())
    if output_start_ts is None:
        output_start_ts = time.monotonic()

    if args.output_fps > 0:
        writer_fps = clamp_fps(args.output_fps)
    elif len(output_frames) >= AUTO_FPS_FRAMES:
        elapsed = max(time.monotonic() - output_start_ts, 1e-6)
        writer_fps = clamp_fps(len(output_frames) / elapsed)
    else:
        return None, output_start_ts, False

    frame_h, frame_w = processed.shape[:2]
    writer = create_writer(args.output, frame_w, frame_h, writer_fps)
    print(f'Output writer started at {writer_fps:.2f} FPS', flush=True)
    for buffered in output_frames:
        writer.write(buffered)
    output_frames.clear()
    return writer, output_start_ts, True


def flush_remaining_output(args, output_frames, output_start_ts, writer):
    if not args.output or writer is not None or not output_frames:
        return writer

    if args.output_fps > 0:
        writer_fps = clamp_fps(args.output_fps)
    else:
        elapsed = max(time.monotonic() - (output_start_ts or time.monotonic()), 1e-6)
        writer_fps = clamp_fps(len(output_frames) / elapsed)

    frame_h, frame_w = output_frames[0].shape[:2]
    writer = create_writer(args.output, frame_w, frame_h, writer_fps)
    print(f'Output writer started at {writer_fps:.2f} FPS (flush)', flush=True)
    for buffered in output_frames:
        writer.write(buffered)
    output_frames.clear()
    return writer


def main():
    args = parse_args()
    camera, source = open_camera(args.device, args.width, args.height, args.fps)

    gui_enabled = not args.no_gui and has_display()
    if gui_enabled:
        print(f'Streaming from {source} with preview window. Press q to quit.', flush=True)
    else:
        print(f'Streaming from {source} in headless mode.', flush=True)
        if not args.no_gui:
            print('No DISPLAY/WAYLAND detected, so preview is disabled automatically.', flush=True)

    writer = None
    output_frames = []
    output_start_ts = None

    frame_count = 0
    tick_start = time.monotonic()

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print('Failed to read frame from camera.', flush=True)
                continue

            processed = process_frame(frame)
            writer, output_start_ts, wrote_current = init_writer_if_ready(
                args=args,
                output_frames=output_frames,
                output_start_ts=output_start_ts,
                writer=writer,
                processed=processed,
            )

            if writer is not None and not wrote_current:
                writer.write(processed)

            if gui_enabled:
                cv2.imshow(WINDOW_NAME, processed)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            frame_count += 1

            if args.max_frames > 0 and frame_count >= args.max_frames:
                break

            if not gui_enabled and frame_count % 30 == 0:
                elapsed = time.monotonic() - tick_start
                fps_now = frame_count / elapsed if elapsed > 0 else 0.0
                print(f'Frames: {frame_count} | Avg FPS: {fps_now:.2f}', flush=True)
    finally:
        writer = flush_remaining_output(args, output_frames, output_start_ts, writer)

        camera.release()
        if writer is not None:
            writer.release()
        if gui_enabled:
            cv2.destroyAllWindows()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
