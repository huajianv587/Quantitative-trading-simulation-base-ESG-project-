from blueprint_runtime import build_memory_output


def load_memory(entries: list[dict] | None = None) -> dict:
    return build_memory_output("relational_memory", entries)
