"""The aria node: streams ego video, eye gaze and microphones, and speaks text on ~/tts."""

import os
import queue
import signal
import threading

from aria.aria_streaming_viewer import AriaStreamingViewer
from aria_msgs.msg import Audio
from geometry_msgs.msg import PointStamped
import numpy as np
import rclpy
import rerun as rr
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image
from std_msgs.msg import String
from std_srvs.srv import SetBool

from aria_driver import config, messages
from aria_driver.glasses import AriaGlasses
from aria_driver.session import Session

# Receiver stream name to viewer callback, for the streams that only the viewer draws.
VIEWER_STREAMS = {'slam': 'image_callback', 'et': 'image_callback',
                  'imu_batch': 'imu_batch_callback', 'barometer': 'barometer_callback',
                  'magnetometer': 'magnetometer_callback', 'hand_pose': 'hand_pose_callback',
                  'vio': 'vio_callback', 'vio_high_frequency': 'vio_high_frequency_callback'}
SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000, 96000)


def patch_rerun_quaternion():
    """rerun-sdk 0.23 passes copy= to np.asarray, which numpy 1.x rejects."""
    def to_array(self, dtype=None, copy=None):
        return np.asarray(self.xyzw, dtype=dtype)
    rr.datatypes.Quaternion.__array__ = to_array


class AriaNode(Node):
    """Own the glasses: publish their streams while streaming is on, and speak ~/tts.

    With viewer.enable, the same samples also go to Meta's Rerun viewer, since one receiver
    gets the glasses' stream.
    """

    def __init__(self):
        super().__init__('aria', automatically_declare_parameters_from_overrides=True)
        self.cfg = config.from_node(self)
        if 'stream' not in self.cfg:
            raise RuntimeError('start the aria node with --ros-args --params-file aria.yaml')
        self.glasses = AriaGlasses(self.cfg.device)
        device, stream = self.cfg.device, self.cfg.stream
        if device.wifi_control and not device.ip and stream.interface != 'usb':
            self.get_logger().info('moving control of the glasses to Wi-Fi, up to 20 s')
            ip = self.glasses.use_wifi()
            where = f'over Wi-Fi at {ip}' if ip else 'over USB: they are not on Wi-Fi'
            self.get_logger().info(f'controlling the glasses {where}')
        patch_rerun_quaternion()
        self.viewer = None
        self.calibrated = False
        if self.cfg.viewer.enable:
            self.viewer = AriaStreamingViewer(jpeg_quality=self.cfg.viewer.jpeg_quality,
                                              rerun_memory_limit=self.cfg.viewer.memory_limit)
        self.session = None
        self.audio_rate = 0

        self.video_pub = self.create_publisher(Image, '~/rgb/image_raw', qos_profile_sensor_data)
        self.gaze_pub = self.create_publisher(PointStamped, '~/gaze', qos_profile_sensor_data)
        self.audio_pub = self.create_publisher(Audio, '~/audio', 100)
        self.create_subscription(String, '~/tts', self.on_tts, 10)
        self.create_service(SetBool, '~/set_streaming', self.on_set_streaming)

        self.speech = queue.Queue()
        threading.Thread(target=self.speak_loop, daemon=True).start()
        if self.cfg.stream.enable:
            self.start_streaming()

    def start_streaming(self):
        self.session = Session(self.cfg) if self.cfg.record.enable else None
        callbacks = {'rgb': self.on_rgb, 'eye_gaze': self.on_gaze, 'audio': self.on_audio,
                     'device_calib': self.on_calibration}
        if self.viewer is not None:
            for name, method in VIEWER_STREAMS.items():
                callbacks[name] = self.viewer_only(getattr(self.viewer, method))
        vrs_path = self.session.vrs_path if self.session is not None else None
        self.glasses.start_streaming(self.cfg.stream, callbacks, vrs_path)
        if self.viewer is not None:
            self.viewer.set_stream_receiver(self.glasses.receiver)
        folder = f', recording to {self.session.folder}' if self.session is not None else ''
        self.get_logger().info(f'streaming over {self.cfg.stream.interface}{folder}')

    def stop_streaming(self):
        self.glasses.stop_streaming()
        if self.session is not None:
            self.session.close()
            self.session = None

    def on_set_streaming(self, request, response):
        try:
            if request.data and not self.glasses.streaming:
                self.start_streaming()
            elif not request.data and self.glasses.streaming:
                self.stop_streaming()
            response.success = True
        except Exception as error:
            response.message = str(error)
        return response

    def stamp(self, stream, capture_ns):
        """Host time of capture: arrival time minus TicSync latency once the clocks sync.

        Args:
            stream: rgb, eye_gaze or audio, for the session's clock log.
            capture_ns: capture time on the glasses' clock.

        Returns:
            builtin_interfaces/Time for the message header.
        """
        host_ns = self.get_clock().now().nanoseconds
        latency_ms = self.glasses.latency_ms(capture_ns)
        session = self.session
        if session is not None:
            session.log_clock(stream, capture_ns, host_ns, latency_ms)
        return messages.to_time(host_ns - (0 if latency_ms is None else int(latency_ms * 1e6)))

    def viewer_only(self, draw):
        """Wrap a viewer callback so it runs once the calibration has arrived."""
        def callback(*args):
            if self.calibrated:
                draw(*args)
        return callback

    def on_calibration(self, device_calib):
        if self.viewer is not None:
            self.viewer.calib_callback(device_calib)
        self.calibrated = True

    def on_rgb(self, image_data, image_record):
        """Publish one ego video frame, pixels (H, W, 3)."""
        pixels = image_data.to_numpy_array()
        stamp = self.stamp('rgb', image_record.capture_timestamp_ns)
        self.video_pub.publish(messages.to_image(pixels, stamp, 'aria_rgb_optical_frame'))
        if self.viewer is not None:
            self.viewer.image_callback(image_data, image_record)

    def on_gaze(self, eye_gaze):
        capture_ns = round(eye_gaze.tracking_timestamp.total_seconds() * 1e9)
        stamp = self.stamp('eye_gaze', capture_ns)
        self.gaze_pub.publish(messages.to_gaze_point(eye_gaze, stamp, self.cfg.gaze.depth))
        if self.viewer is not None:
            self.viewer.eye_gaze_callback(eye_gaze)

    def on_audio(self, audio_data, audio_record, channels):
        """Publish one block of N samples on M channels, with one device timestamp per sample."""
        times = audio_record.capture_timestamps_ns
        if len(times) == 0:
            return
        if len(times) > 1 and times[-1] > times[0]:
            measured = (len(times) - 1) * 1e9 / (times[-1] - times[0])
            self.audio_rate = min(SAMPLE_RATES, key=lambda rate: abs(rate - measured))
        samples = np.asarray(audio_data.data, dtype=np.int32)
        stamp = self.stamp('audio', times[0])
        self.audio_pub.publish(messages.to_audio(samples, channels, self.audio_rate, stamp))
        # The viewer labels microphones from the calibration.
        if self.viewer is not None and self.calibrated:
            self.viewer.audio_callback(audio_data, audio_record, channels)

    def on_tts(self, message):
        text = message.data.strip()
        if text:
            self.speech.put(text)

    def speak_loop(self):
        """Speak queued text one utterance at a time, off the ROS executor."""
        while True:
            text = self.speech.get()
            try:
                self.glasses.speak(text)
                self.get_logger().info(f'said: {text}')
            except Exception as error:
                self.get_logger().error(f'TTS failed: {error}')

    def close(self):
        """Stop streaming and disconnect, forcing exit when the SDK hangs."""
        watchdog = threading.Timer(self.cfg.stream.shutdown_timeout, os._exit, (1,))
        watchdog.daemon = True
        watchdog.start()
        self.stop_streaming()
        self.glasses.disconnect()
        watchdog.cancel()


def main(args=None):
    # Ctrl+C and launch's SIGTERM raise KeyboardInterrupt instead of shutting ROS down, so
    # the SDK callbacks still publish until close() stops the stream.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = AriaNode()
    try:
        while rclpy.ok():  # a timeout returns to Python, which raises KeyboardInterrupt
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
