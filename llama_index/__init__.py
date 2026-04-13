from __future__ import annotations

import site
from pathlib import Path
from pkgutil import extend_path


_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent.resolve()


def _discover_external_paths() -> list[str]:
    candidates: list[str] = []
    search_roots = list(site.getsitepackages())
    try:
        user_site = site.getusersitepackages()
        if user_site:
            search_roots.append(user_site)
    except Exception:
        pass

    for root in search_roots:
        package_dir = Path(root) / "llama_index"
        if not package_dir.exists():
            continue
        resolved = package_dir.resolve()
        if resolved == _CURRENT_DIR:
            continue
        candidates.append(str(resolved))

    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


_external_paths = _discover_external_paths()
__path__ = [*_external_paths, *_discover_external_paths(), *extend_path(__path__, __name__)]

_deduped_path: list[str] = []
_seen_path: set[str] = set()
for _item in __path__:
    _resolved = str(Path(_item).resolve())
    if _resolved == str(_PROJECT_ROOT):
        continue
    if _resolved in _seen_path:
        continue
    _seen_path.add(_resolved)
    _deduped_path.append(_item)
__path__ = _deduped_path

__all__ = ["core", "retrievers", "embeddings", "vector_stores"]
