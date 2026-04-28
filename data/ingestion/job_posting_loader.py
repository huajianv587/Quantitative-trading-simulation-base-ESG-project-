from blueprint_runtime import build_dataset_output


def load_dataset(symbols: list[str] | None = None) -> dict:
    return build_dataset_output("job_posting_loader", symbols)
