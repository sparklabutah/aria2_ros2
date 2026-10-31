"""Check the glasses from a terminal: status, profiles, and on-device recordings."""

import argparse
import json
import os

from ament_index_python.packages import get_package_share_directory

from aria_driver import config
from aria_driver.glasses import AriaGlasses


def parse_args():
    default = os.path.join(get_package_share_directory('aria_driver'), 'config', 'aria.yaml')
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='Trailing key=value pairs override the file, such as device.ip=10.0.0.5.')
    parser.add_argument('--config', default=default, help='ROS parameter file of the aria node')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('info', help='serial, battery, Wi-Fi and thermal status')
    commands.add_parser('profiles', help='recording and streaming profiles')
    commands.add_parser('recordings', help='recordings stored on the glasses')
    record = commands.add_parser('record', help='record on the glasses with stream.profile')
    record.add_argument('--name', required=True)
    record.add_argument('--seconds', type=float, required=True)
    download = commands.add_parser('download', help='copy one recording to this host')
    download.add_argument('uuid')
    download.add_argument('--output', default='data/downloads')
    args, args.overrides = parser.parse_known_args()
    unknown = [item for item in args.overrides if '=' not in item]
    if unknown:
        parser.error(f'unrecognized arguments: {" ".join(unknown)}')
    return args


def main():
    args = parse_args()
    cfg = config.load(args.config, args.overrides)
    glasses = AriaGlasses(cfg.device)
    try:
        if args.command == 'info':
            result = glasses.info()
        elif args.command == 'profiles':
            result = glasses.profiles()
        elif args.command == 'recordings':
            result = glasses.recordings()
        elif args.command == 'record':
            result = {'uuid': glasses.record(args.name, args.seconds, cfg.stream.profile)}
        else:
            result = {'output': glasses.download(args.uuid, args.output)}
    finally:
        glasses.disconnect()
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
