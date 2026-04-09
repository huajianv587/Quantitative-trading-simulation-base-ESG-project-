from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path


def _load_real_package():
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.resolve()
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


_real_module = _load_real_package()

if _real_module is not None:
    globals().update(_real_module.__dict__)
else:
    __all__ = ["core", "retrievers", "embeddings"]

