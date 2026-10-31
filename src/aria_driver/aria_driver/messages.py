"""Aria samples as ROS messages.

Shape letters: H, W image height and width; C image channels; N audio samples per channel;
M microphone channels.
"""

import array

from aria_msgs.msg import Audio
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PointStamped
import numpy as np
from projectaria_tools.core.mps import get_eyegaze_point_at_depth
from sensor_msgs.msg import Image

ENCODINGS = {1: 'mono8', 3: 'rgb8', 4: 'rgba8'}


def to_time(ns):
    return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)


def to_image(pixels, stamp, frame_id):
    """Pack one camera frame.

    Args:
        pixels (H, W) or (H, W, C): uint8 image.
        stamp: header time.
        frame_id: optical frame of the camera.

    Returns:
        sensor_msgs/Image, mono8, rgb8 or rgba8.
    """
    height, width = pixels.shape[:2]
    channels = 1 if pixels.ndim == 2 else pixels.shape[2]
    message = Image(height=height, width=width, encoding=ENCODINGS[channels],
                    step=width * channels)
    message.header.stamp, message.header.frame_id = stamp, frame_id
    message.data = array.array('B', np.ascontiguousarray(pixels).tobytes())
    return message


def to_audio(samples, channels, sample_rate, stamp):
    """Pack one block of microphone samples.

    Args:
        samples (N * M,): interleaved int32 samples.
        channels: M.
        sample_rate: samples per second per channel.
        stamp: host time of the first sample.

    Returns:
        aria_msgs/Audio.
    """
    message = Audio(sample_rate=sample_rate, channels=channels)
    message.header.stamp, message.header.frame_id = stamp, 'aria_microphones'
    message.data = array.array('i', samples.astype(np.int32).tobytes())
    return message


def to_gaze_point(eye_gaze, stamp, fallback_depth):
    """Where the wearer looks, in the central pupil frame (CPF).

    Args:
        eye_gaze: projectaria_tools EyeGaze.
        stamp: header time.
        fallback_depth: metres along the gaze ray when the glasses report no depth.

    Returns:
        geometry_msgs/PointStamped in frame aria_cpf: the vergence point when valid, else the
        gaze ray at the reported or fallback depth.
    """
    if eye_gaze.spatial_gaze_point_valid:
        point = np.asarray(eye_gaze.spatial_gaze_point_in_cpf, dtype=float).reshape(3)
    else:
        depth = eye_gaze.depth if eye_gaze.depth > 0 else fallback_depth
        point = get_eyegaze_point_at_depth(eye_gaze.yaw, eye_gaze.pitch, depth).reshape(3)
    message = PointStamped()
    message.header.stamp, message.header.frame_id = stamp, 'aria_cpf'
    message.point.x, message.point.y, message.point.z = (float(value) for value in point)
    return message
