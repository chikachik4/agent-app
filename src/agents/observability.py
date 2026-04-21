from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.tools.metrics_tools import (
    check_metric_threshold,
    get_error_rate,
    get_pod_restart_count,
    query_prometheus,
)


class ObservabilityAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 시스템 관측(Observability) 전문가입니다. "
            "Prometheus 메트릭을 분석하여 서비스 상태, 에러율, 트래픽 변화를 파악합니다.\n\n"
            "도구 선택 가이드:\n"
            "- check_metric_threshold: 임계치 초과 여부를 EXCEEDED/OK로 반환 (롤백 판단 시 최우선 사용)\n"
            "- get_error_rate: 서비스 5xx 에러율 상세 조회\n"
            "- get_pod_restart_count: Pod 재시작 횟수 조회\n"
            "- query_prometheus: 직접 PromQL 실행\n\n"
            "임계치 확인이 요청된 경우 반드시 check_metric_threshold를 호출하고 "
            "EXCEEDED/OK 상태를 응답에 명시하세요. "
            "메트릭이 없거나 조회 실패 시에도 가능한 정보를 제공하세요."
        )

    def get_tools(self) -> list:
        return [check_metric_threshold, query_prometheus, get_error_rate, get_pod_restart_count]
