from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path


def _load_real_module():
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.resolve()
    search_paths: list[str] = []

    for entry in sys.path:
        resolved = Path(entry or ".").resolve()
        if resolved == project_root:
            continue
        search_paths.append(str(resolved))

    spec = importlib.machinery.PathFinder.find_spec(__name__, search_paths)
    if spec is None or spec.loader is None or not spec.origin:
        return None

    origin = Path(spec.origin).resolve()
    if origin == current_file:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[__name__] = module
    spec.loader.exec_module(module)
    return module


_real_module = _load_real_module()

if _real_module is not None:
    globals().update(_real_module.__dict__)
else:
    _jobs = []

    class _Job:
        def __init__(self, interval: int = 1) -> None:
            self.interval = interval
            self.unit = None
            self.when = None
            self.func = None
            self.args = ()
            self.kwargs = {}

        @property
        def day(self):
            self.unit = "day"
            return self

        @property
        def monday(self):
            self.unit = "monday"
            return self

        @property
        def minutes(self):
            self.unit = "minutes"
            return self

        def at(self, when: str):
            self.when = when
            return self

        def do(self, func, *args, **kwargs):
            self.func = func
            self.args = args
            self.kwargs = kwargs
            _jobs.append(self)
            return self

    def every(interval: int = 1):
        return _Job(interval=interval)

    def run_pending():
        return None

