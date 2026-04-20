from abc import ABC, abstractmethod
from strands import Agent
from strands.models.bedrock import BedrockModel


class BaseAgent(ABC):
    def __init__(self, model: BedrockModel) -> None:
        self._agent = Agent(
            model=model,
            tools=self.get_tools(),
            system_prompt=self.system_prompt,
        )

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def get_tools(self) -> list: ...

    def run(self, prompt: str) -> str:
        return str(self._agent(prompt))
