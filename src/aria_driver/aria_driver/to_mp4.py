"""Convert a streaming session's VRS recordings to MP4 video with the microphones' sound."""

import argparse
import os
from pathlib import Path
import shutil

from ament_index_python.packages import get_package_share_directory
from projectaria_tools.tools.vrs_to_mp4.vrs_to_mp4_utils import convert_vrs_to_mp4

from aria_driver import config


def newest_session(root):
    """Find the newest session that holds a recording.

    Args:
        root: folder of session folders, whose names start with their UTC start time.

    Returns:
        The session folder.
    """
    recordings = sorted(root.glob('*/vrs/*.vrs'))
    if not recordings:
        raise SystemExit(f'No recordings in {root}')
    return recordings[-1].parents[1]


def session_to_mp4(session, output_dir):
    """Convert each VRS file of one session, keeping MP4 files that already exist.

    Args:
        session: the session folder.
        output_dir: folder for the MP4 files.

    Returns:
        The MP4 paths, one per connection of the glasses.
    """
    mp4_paths = []
    for vrs_path in sorted(session.glob('vrs/*.vrs')):
        mp4_path = output_dir / f"{session.name}_{vrs_path.stem.replace(':', '-')}.mp4"
        if not mp4_path.exists():
            convert_vrs_to_mp4(str(vrs_path), str(mp4_path))
        mp4_paths.append(mp4_path)
    return mp4_paths


def parse_args():
    default = os.path.join(get_package_share_directory('aria_driver'), 'config', 'aria.yaml')
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='Trailing key=value pairs override the file, such as record.video_dir=/tmp/videos.')
    parser.add_argument('--config', default=default, help='ROS parameter file of the aria node')
    parser.add_argument('--session', help='session name or folder; the newest one by default')
    args, args.overrides = parser.parse_known_args()
    unknown = [item for item in args.overrides if '=' not in item]
    if unknown:
        parser.error(f'unrecognized arguments: {" ".join(unknown)}')
    return args


def main():
    args = parse_args()
    cfg = config.load(args.config, args.overrides)
    # The converter calls both only after minutes of encoding.
    for binary in ('ffmpeg', 'ffprobe'):
        if shutil.which(binary) is None:
            raise SystemExit(f'{binary} not found; run `sudo apt install ffmpeg` once')
    root = Path(cfg.record.output_dir).expanduser().resolve()
    if args.session is None:
        session = newest_session(root)
    else:
        session = Path(args.session) if Path(args.session).is_dir() else root / args.session
    output_dir = Path(cfg.record.video_dir).expanduser().resolve()
    mp4_paths = session_to_mp4(session, output_dir)
    if not mp4_paths:
        raise SystemExit(f'No recordings in {session}')
    for mp4_path in mp4_paths:
        print(mp4_path)


if __name__ == '__main__':
    main()
