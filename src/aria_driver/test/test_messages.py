from types import SimpleNamespace

from aria_driver import messages
import numpy as np


def eye_gaze(yaw, pitch, depth, spatial=None):
    return SimpleNamespace(yaw=yaw, pitch=pitch, depth=depth,
                           spatial_gaze_point_valid=spatial is not None,
                           spatial_gaze_point_in_cpf=spatial)


def test_to_image_packs_rgb_and_mono():
    stamp = messages.to_time(1_500_000_000)
    rgb = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    message = messages.to_image(rgb, stamp, 'aria_rgb_optical_frame')
    assert (message.height, message.width, message.encoding, message.step) == (4, 6, 'rgb8', 18)
    assert bytes(message.data) == rgb.tobytes()
    assert (message.header.stamp.sec, message.header.stamp.nanosec) == (1, 500_000_000)
    mono = messages.to_image(rgb[..., 0], stamp, 'aria_rgb_optical_frame')
    assert (mono.encoding, mono.step, len(mono.data)) == ('mono8', 6, 24)


def test_to_audio_keeps_samples():
    samples = np.array([-(2 ** 31), -1, 0, 1, 2 ** 31 - 1, 7], dtype=np.int32)
    message = messages.to_audio(samples, 2, 48000, messages.to_time(0))
    assert (message.channels, message.sample_rate) == (2, 48000)
    assert list(message.data) == samples.tolist()


def test_gaze_point_prefers_the_vergence_point():
    spatial = np.array([[0.1], [0.2], [0.9]])
    message = messages.to_gaze_point(eye_gaze(0.3, 0.1, 2.0, spatial), messages.to_time(0), 1.0)
    assert message.header.frame_id == 'aria_cpf'
    assert np.allclose([message.point.x, message.point.y, message.point.z], [0.1, 0.2, 0.9])


def test_gaze_point_falls_back_to_the_given_depth():
    straight = messages.to_gaze_point(eye_gaze(0.0, 0.0, 0.0), messages.to_time(0), 1.5).point
    assert np.allclose([straight.x, straight.y, straight.z], [0.0, 0.0, 1.5])
    reported = messages.to_gaze_point(eye_gaze(0.0, 0.0, 0.5), messages.to_time(0), 1.5).point
    assert np.allclose([reported.x, reported.y, reported.z], [0.0, 0.0, 0.5])
