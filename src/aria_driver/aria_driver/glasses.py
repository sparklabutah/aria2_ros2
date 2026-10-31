"""Project Aria Gen2 glasses through the Client SDK: connection, streaming, recording, TTS."""

import json
from pathlib import Path
import threading
import time

import aria.sdk_gen2 as sdk
from aria.stream_receiver import StreamReceiver

# Written by `aria_gen2 streaming install-certs`; the receiver serves TLS with this cert.
CERTS_DIR = Path.home() / '.aria' / 'streaming-certs' / 'persistent'


class AriaGlasses:
    """One pair of glasses, controlled over USB or the LAN."""

    def __init__(self, cfg):
        """Connect to the glasses.

        Args:
            cfg: the device block; ip connects over Wi-Fi, and both ip and serial empty
                picks the first USB device.
        """
        self.client = sdk.DeviceClient()
        self.client.set_client_config(sdk.DeviceClientConfig())
        self.device = self.client.connect(sdk.DeviceTarget(ip=cfg.ip, serial=cfg.serial))
        self.receiver = None
        self.lock = threading.Lock()

    def use_wifi(self):
        """Reconnect over the glasses' Wi-Fi, so the USB cable can come off.

        Returns:
            The glasses' Wi-Fi IP address, or None when they are not on Wi-Fi.
        """
        status = self.device.status()
        if not status.wifi_connected:
            return None
        # Both connections share the serial as their id, so the USB one goes first.
        self.client.disconnect(self.device)
        self.device = self.client.connect(sdk.DeviceTarget(ip=status.wifi_ip_address))
        return status.wifi_ip_address

    @property
    def streaming(self):
        return self.receiver is not None

    def start_streaming(self, cfg, callbacks, vrs_path=None):
        """Start a receiver on this host, then have the glasses stream to it.

        Args:
            cfg: the stream block, with interface, profile, host and port.
            callbacks: receiver stream name to callback, such as {'rgb': on_rgb}.
            vrs_path: folder the receiver records every stream into, one VRS file per
                connection of the glasses, or None.
        """
        interfaces = {'usb': sdk.StreamingInterface.USB_NCM,
                      'wifi_sta': sdk.StreamingInterface.WIFI_STA,
                      'wifi_sap': sdk.StreamingInterface.WIFI_SAP}
        streaming = sdk.HttpStreamingConfig()
        streaming.profile_name = cfg.profile
        streaming.streaming_interface = interfaces[cfg.interface]
        # Without a cert name the SDK makes a new cert per start and rewrites the receiver's key.
        cert_name = CERTS_DIR / 'publisher-cert-name'
        if not cert_name.is_file():
            raise RuntimeError(f'No streaming cert in {CERTS_DIR}; run '
                               '`aria_gen2 streaming install-certs` once')
        streaming.streaming_cert_name = cert_name.read_text().strip()
        if self.device.is_recording():
            raise RuntimeError('The glasses are recording (aria_device record); '
                               'stream once it finishes')
        if self.device.is_streaming():  # left over from a run that was killed
            self.device.stop_streaming()
        self.device.set_streaming_config(streaming)

        server = sdk.HttpServerConfig()
        server.address, server.port = cfg.host, cfg.port
        receiver = StreamReceiver(enable_image_decoding=True, enable_raw_stream=False)
        receiver.set_server_config(server)
        if vrs_path is not None:
            receiver.record_to_vrs(str(vrs_path))
        for name, callback in callbacks.items():
            getattr(receiver, f'register_{name}_callback')(callback)
        receiver.start_server()
        try:
            self.device.start_streaming()
        except Exception:
            receiver.stop_server()
            raise
        self.receiver = receiver

    def stop_streaming(self):
        # Callbacks run until the server stops, but TicSync state dies with the stream.
        with self.lock:
            receiver, self.receiver = self.receiver, None
        if receiver is None:  # the stream, if any, belongs to another process
            return
        if self.device.is_streaming():
            self.device.stop_streaming()
        receiver.stop_server()

    def latency_ms(self, capture_ns):
        """Transport latency of one sample, or None until TicSync has synced the clocks.

        Args:
            capture_ns: capture time on the glasses' clock.

        Returns:
            Milliseconds from capture on the glasses to now on this host.
        """
        with self.lock:
            sync = self.receiver.get_time_sync() if self.receiver is not None else None
            if sync is None or not sync.is_valid():
                return None
            return sync.compute_latency_ms(capture_ns)

    def speak(self, text):
        self.device.render_tts(text=text)

    def info(self):
        status = self.device.status()
        fields = ('battery_level', 'charging', 'wifi_connected', 'wifi_ip_address', 'wifi_ssid',
                  'developer_mode', 'thermal_mitigation_triggered', 'skin_temp_celsius')
        info = {'serial': self.device.serial()}
        for field in fields:
            value = getattr(status, field, None)
            info[field] = getattr(value, 'name', value)
        return info

    def profiles(self):
        return {group: {profile.name: profile.description for profile in listing.profiles}
                for group, listing in self.device.device_profiles().items()}

    def recordings(self):
        return [{'name': recording.name, 'size': recording.size,
                 'metadata': json.loads(recording.metadata or 'null')}
                for recording in self.device.list_recordings()]

    def record(self, name, seconds, profile):
        """Record on the glasses for a fixed time.

        Returns:
            The recording's id, which download takes.
        """
        if self.device.is_streaming():
            raise RuntimeError('The glasses are streaming to an aria node; stop it, or call '
                               '/aria/set_streaming with data: false, then record')
        recording = sdk.RecordingConfig()
        recording.recording_name, recording.profile_name = name, profile
        self.device.set_recording_config(recording)
        uuid = self.device.start_recording()
        try:
            time.sleep(seconds)
        finally:
            self.device.stop_recording()
        return uuid

    def download(self, uuid, output_dir):
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        self.device.download_recording(uuid=uuid, output_path=str(output))
        return output

    def disconnect(self):
        # record() stops its own recording, so a recording here belongs to another process.
        self.stop_streaming()
        self.client.disconnect(self.device)
