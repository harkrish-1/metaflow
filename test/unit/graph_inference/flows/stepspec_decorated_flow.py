from metaflow import StepSpec, Parameter, retry


@retry(times=3)
class StepSpecDecoratedFlow(StepSpec):
    text = Parameter("text", type=str, default="hello")

    def call(self):
        self.output = self.text.upper()


if __name__ == "__main__":
    StepSpecDecoratedFlow()
