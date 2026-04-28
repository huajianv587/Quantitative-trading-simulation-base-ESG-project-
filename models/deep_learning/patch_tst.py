from blueprint_runtime import BlueprintModelAdapter


class ModelAdapter(BlueprintModelAdapter):
    def __init__(self, name: str = "patch_tst") -> None:
        super().__init__(name=name)
