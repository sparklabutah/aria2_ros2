"""Speak through the glasses from a terminal: each typed line goes to /aria/tts."""

import rclpy
from std_msgs.msg import String


def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node('tts_prompt')
    publisher = node.create_publisher(String, '/aria/tts', 10)
    print('Type a line and press Enter for the glasses to say it; Ctrl+D quits.')
    try:
        while True:
            publisher.publish(String(data=input('say> ')))
    except (EOFError, KeyboardInterrupt):
        print()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
