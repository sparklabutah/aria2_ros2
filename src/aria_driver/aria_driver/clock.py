"""Offline map from the glasses' capture clock to the host clock, fit on a session's clock.csv.

Shape letters: T timestamps.
"""

import numpy as np


class ClockFit:
    """Least-squares line host_ns = origin + rate * (capture_ns - capture_origin)."""

    def __init__(self, path, stream):
        """Fit one stream of a session.

        Rows with a TicSync latency are fit at arrival time minus latency; without any,
        every row is fit at arrival time.

        Args:
            path: a session's clock.csv.
            stream: rgb, eye_gaze or audio.
        """
        rows = np.genfromtxt(path, delimiter=',', names=True, dtype=None, encoding='utf-8')
        rows = np.atleast_1d(rows)
        rows = rows[rows['stream'] == stream]
        synced = ~np.isnan(rows['latency_ms'])
        if synced.sum() >= 2:
            rows = rows[synced]
        if len(rows) < 2:
            raise ValueError(f'clock.csv has fewer than two {stream} rows')
        latency_ns = np.nan_to_num(rows['latency_ms']) * 1e6
        self.capture_origin, self.host_origin = rows['capture_ns'][0], rows['host_ns'][0]
        capture = (rows['capture_ns'] - self.capture_origin).astype(float)
        host = (rows['host_ns'] - self.host_origin).astype(float) - latency_ns
        self.rate, self.offset = np.polyfit(capture, host, 1)
        self.rms_ns = float(np.sqrt(np.mean((host - self.rate * capture - self.offset) ** 2)))

    def map(self, capture_ns):
        """Host times of capture times.

        Args:
            capture_ns (T,): capture times on the glasses' clock.

        Returns:
            host_ns (T,): int64 times on the host clock.
        """
        delta = np.asarray(capture_ns, dtype=np.int64) - self.capture_origin
        return self.host_origin + np.round(self.offset + self.rate * delta).astype(np.int64)
