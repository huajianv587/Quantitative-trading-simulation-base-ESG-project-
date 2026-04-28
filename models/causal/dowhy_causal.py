from blueprint_runtime import BlueprintModelAdapter


class ModelAdapter(BlueprintModelAdapter):
    def __init__(self, name: str = "dowhy_causal") -> None:
        super().__init__(name=name)
