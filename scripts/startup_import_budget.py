from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FORBIDDEN_PREFIXES = (
    "llama_index",
    "sentence_transformers",
    "gateway.rag.rag_main",
    "gateway.rag.embeddings",
    "torch",
    "transformers",
)
NEXT_TARGET_PREFIXES: tuple[str, ...] = (
    "gateway.quant.service_components",
    "gateway.quant.paper_services",
)


def _loaded(prefixes: tuple[str, ...]) -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
    )


def _loaded_counts(prefixes: tuple[str, ...]) -> dict[str, int]:
    return {
        prefix: sum(
            1
            for name in sys.modules
            if name == prefix or name.startswith(f"{prefix}.")
        )
        for prefix in prefixes
    }


def main() -> int:
    import gateway.main  # noqa: F401

    forbidden_loaded = _loaded(FORBIDDEN_PREFIXES)
    next_target_counts = _loaded_counts(NEXT_TARGET_PREFIXES)
    report = {
        "ok": not forbidden_loaded,
        "forbidden_prefixes": FORBIDDEN_PREFIXES,
        "forbidden_loaded": forbidden_loaded,
        "next_split_targets_loaded": [
            prefix for prefix, count in next_target_counts.items() if count
        ],
        "next_split_target_module_counts": next_target_counts,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not forbidden_loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
