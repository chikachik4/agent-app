from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.tools.chaos_tools import inject_fault, recover_fault


class ChaosAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 카오스 엔지니어링 전문가입니다. "
            "Kubernetes 환경에서 의도적인 장애를 주입하여 시스템의 회복력을 검증하는 역할을 합니다. "
            "주어진 도구를 사용하여 Pod 삭제, 네트워크 지연 등의 장애를 정확하게 실행하고 "
            "실행 결과를 명확하게 보고하세요. "
            "장애 주입 전에 항상 대상 리소스와 네임스페이스를 확인하세요."
        )

    def get_tools(self) -> list:
        return [inject_fault, recover_fault]
