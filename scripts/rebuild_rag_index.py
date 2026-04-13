import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.rag.rag_main import get_query_engine


def main() -> None:
    print("[RAG] Starting forced index rebuild with document cleaning enabled...")
    get_query_engine(force_rebuild=True)
    print("[RAG] Forced index rebuild completed.")


if __name__ == "__main__":
    main()
