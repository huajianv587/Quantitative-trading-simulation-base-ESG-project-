from blueprint_runtime import BlueprintModelAdapter


class ModelAdapter(BlueprintModelAdapter):
    def __init__(self, name: str = "ppo_agent") -> None:
        super().__init__(name=name)
