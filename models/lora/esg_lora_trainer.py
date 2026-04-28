from blueprint_runtime import BlueprintModelAdapter


class ModelAdapter(BlueprintModelAdapter):
    def __init__(self, name: str = "esg_lora_trainer") -> None:
        super().__init__(name=name)
