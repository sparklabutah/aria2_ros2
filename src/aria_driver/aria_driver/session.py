"""One streaming session on disk: the run's settings, the VRS recording, and a clock log."""

from datetime import datetime, timezone
from pathlib import Path
import threading
import uuid

from aria_driver import config


class Session:
    """A new folder per streaming session, never reused.

    The folder holds config.yaml, vrs/, and clock.csv, whose rows tie each sample's
    capture time on the glasses to this host's clock.
    """

    def __init__(self, cfg):
        """Make the folder and save the settings into it.

        Args:
            cfg: all settings; cfg.record.output_dir is the parent folder.
        """
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        root = Path(cfg.record.output_dir).expanduser().resolve()
        self.folder = root / f'{stamp}_{uuid.uuid4().hex[:8]}'
        self.folder.mkdir(parents=True, exist_ok=False)
        config.save(cfg, self.folder / 'config.yaml')
        self.vrs_path = self.folder / 'vrs'
        self.clock = open(self.folder / 'clock.csv', 'w')
        self.clock.write('stream,capture_ns,host_ns,latency_ms\n')
        self.lock = threading.Lock()

    def log_clock(self, stream, capture_ns, host_ns, latency_ms):
        """Record when one sample was captured and when it arrived.

        Args:
            stream: rgb, eye_gaze or audio.
            capture_ns: capture time on the glasses' clock.
            host_ns: arrival time on this host's ROS clock.
            latency_ms: TicSync transport latency, or None before the clocks sync.
        """
        latency_ms = float('nan') if latency_ms is None else latency_ms
        with self.lock:
            if not self.clock.closed:
                self.clock.write(f'{stream},{capture_ns},{host_ns},{latency_ms}\n')

    def close(self):
        with self.lock:
            self.clock.close()
