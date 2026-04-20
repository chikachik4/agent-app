from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.tools.metrics_tools import get_error_rate, get_pod_restart_count, query_prometheus


class ObservabilityAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 시스템 관측(Observability) 전문가입니다. "
            "Prometheus 메트릭을 분석하여 서비스 상태, 에러율, 트래픽 변화를 파악합니다. "
            "카오스 실험 전후의 메트릭 변화를 비교하고 이상 징후를 탐지하여 "
            "명확한 수치와 함께 결과를 보고하세요. "
            "메트릭이 없거나 조회 실패 시에도 가능한 정보를 제공하세요."
        )

    def get_tools(self) -> list:
        return [query_prometheus, get_error_rate, get_pod_restart_count]
