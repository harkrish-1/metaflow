from metaflow import StepSpec, Parameter
from metaflow.user_configs.config_parameters import Config


class StepSpecConfigFlow(StepSpec):
    cfg = Config("cfg", default_value={"multiplier": 3})
    value = Parameter("value", type=int, default=10)

    def call(self):
        self.result = self.value * self.cfg["multiplier"]


if __name__ == "__main__":
    StepSpecConfigFlow()
