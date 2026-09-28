"""Cross-state helper that needs STATE_REGISTRY without the side effects of
importing 00_config.py the normal way (which reads STATE from the
environment, raises SystemExit if it's unset/unknown, and creates a full
directory tree for whichever one state that env var names). Scripts that
operate across ALL states -- the data-quality audit, the pooled classifier,
the dashboard -- import this instead.
"""
import importlib.util as _u
import os
import pathlib as _p


def iter_states():
    """Yields (code, name) for every state in STATE_REGISTRY, in the order
    states were added to the project (IL first).
    """
    prev = os.environ.get("STATE")
    os.environ["STATE"] = "IL"  # any valid code; only needed so 00_config
                                 # doesn't SystemExit while we read the dict
    spec = _u.spec_from_file_location(
        "cfg_probe", _p.Path(__file__).with_name("00_config.py"))
    cfg = _u.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    if prev is None:
        os.environ.pop("STATE", None)
    else:
        os.environ["STATE"] = prev
    for code, s in cfg.STATE_REGISTRY.items():
        yield code, s["name"]
