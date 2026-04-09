
class ModelAdapter:
    def __init__(self, name: str = "lstm_predictor") -> None:
        self.name = name

    def fit(self, X=None, y=None) -> dict:
        return {"model": self.name, "status": "fit_ready"}

    def predict(self, X=None) -> list[float]:
        return [0.0]
