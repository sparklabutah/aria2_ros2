from addict import Dict
from aria_driver import config
from aria_driver.clock import ClockFit
from aria_driver.session import Session
import numpy as np


def make_cfg(root):
    cfg = Dict({'record': {'enable': True, 'output_dir': str(root)}, 'stream': {'port': 6768}})
    cfg.freeze()
    return cfg


def test_sessions_get_their_own_folder_and_config(tmp_path):
    cfg = make_cfg(tmp_path)
    first, second = Session(cfg), Session(cfg)
    assert first.folder != second.folder
    assert config.load(first.folder / 'config.yaml') == cfg
    assert first.vrs_path == first.folder / 'vrs'
    first.close()
    first.log_clock('rgb', 1, 2, None)
    second.close()


def test_clock_fit_recovers_rate_and_latency(tmp_path):
    session = Session(make_cfg(tmp_path))
    capture = np.arange(0, 2_000_000_000, 33_000_000)
    host_origin = 1_788_550_321_000_000_000
    for capture_ns in capture:
        session.log_clock('rgb', capture_ns, host_origin + capture_ns + 5_000_000, 5.0)
        session.log_clock('audio', capture_ns, host_origin + 2 * capture_ns, None)
    session.close()
    fit = ClockFit(session.folder / 'clock.csv', 'rgb')
    assert abs(fit.rate - 1.0) < 1e-9 and fit.rms_ns < 1.0
    assert fit.map([3_000_000_000])[0] == host_origin + 3_000_000_000
    assert abs(ClockFit(session.folder / 'clock.csv', 'audio').rate - 2.0) < 1e-9
