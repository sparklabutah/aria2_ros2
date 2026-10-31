from types import SimpleNamespace

from aria_driver import config
import pytest

PARAMS = """
aria:
  ros__parameters:
    device: {ip: '', serial: ''}
    stream: {interface: wifi_sta, port: 6768}
"""


def test_load_applies_overrides_and_freezes(tmp_path):
    path = tmp_path / 'aria.yaml'
    path.write_text(PARAMS)
    cfg = config.load(path, ['stream.interface=usb', 'device.ip=10.0.0.5', 'gaze.depth=2.0'])
    assert cfg.stream.interface == 'usb'
    assert cfg.stream.port == 6768
    assert cfg.device.ip == '10.0.0.5'
    assert cfg.gaze.depth == 2.0
    with pytest.raises(KeyError):
        cfg.stream.prot


def test_from_node_nests_dotted_names():
    params = {'stream.port': 6768, 'record.enable': True, 'use_sim_time': False}
    node = SimpleNamespace(get_parameters_by_prefix=lambda prefix: {
        name: SimpleNamespace(value=value) for name, value in params.items()})
    cfg = config.from_node(node)
    assert cfg.stream.port == 6768
    assert cfg.record.enable is True


def test_save_round_trips(tmp_path):
    path = tmp_path / 'aria.yaml'
    path.write_text(PARAMS)
    cfg = config.load(path)
    config.save(cfg, tmp_path / 'saved.yaml')
    assert config.load(tmp_path / 'saved.yaml') == cfg
