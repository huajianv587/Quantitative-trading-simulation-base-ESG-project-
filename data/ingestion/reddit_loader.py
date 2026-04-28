from blueprint_runtime import build_dataset_output


def load_dataset(symbols: list[str] | None = None) -> dict:
    return build_dataset_output("reddit_loader", symbols)
