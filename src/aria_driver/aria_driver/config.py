"""Run settings as a frozen addict Dict, read from ROS parameters or a ROS parameter file."""

from addict import Dict
import yaml


def assign(cfg, name, value):
    """Set one dotted name, such as stream.port, creating its blocks on the way.

    Args:
        cfg: an unfrozen Dict.
        name: dotted parameter name.
        value: the value to store.
    """
    *blocks, key = name.split('.')
    for block in blocks:
        cfg = cfg[block]
    cfg[key] = value


def from_node(node):
    """Collect every parameter a node was started with.

    Args:
        node: an rclpy node made with automatically_declare_parameters_from_overrides.

    Returns:
        A frozen Dict with one block per settings group, such as cfg.stream.port.
    """
    cfg = Dict()
    for name, parameter in node.get_parameters_by_prefix('').items():
        assign(cfg, name, parameter.value)
    cfg.freeze()
    return cfg


def load(path, overrides=(), node_name='aria'):
    """Read one node's settings from a ROS parameter file, then apply overrides.

    Args:
        path: ROS parameter file, such as config/aria.yaml.
        overrides: key=value strings, such as device.ip=192.168.1.20.
        node_name: whose ros__parameters to read.

    Returns:
        A frozen Dict, the same shape from_node gives.
    """
    with open(path) as file:
        cfg = Dict(yaml.safe_load(file)[node_name]['ros__parameters'])
    for override in overrides:
        name, value = override.split('=', 1)
        assign(cfg, name, yaml.safe_load(value))
    cfg.freeze()
    return cfg


def save(cfg, path, node_name='aria'):
    """Write settings as a ROS parameter file that starts the same run again.

    Args:
        cfg: settings Dict.
        path: output file.
        node_name: the node the file configures.
    """
    with open(path, 'w') as file:
        yaml.safe_dump({node_name: {'ros__parameters': cfg.to_dict()}}, file, sort_keys=False)
