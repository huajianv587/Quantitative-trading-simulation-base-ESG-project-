from blueprint_runtime import BlueprintModelAdapter


class ModelAdapter(BlueprintModelAdapter):
    def __init__(self, name: str = "xgb_lgb_scorer") -> None:
        super().__init__(name=name)
