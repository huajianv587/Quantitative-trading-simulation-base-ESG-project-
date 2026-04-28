from blueprint_runtime import build_dataset_output


def load_dataset(symbols: list[str] | None = None) -> dict:
    return build_dataset_output("sec_edgar_loader", symbols)
