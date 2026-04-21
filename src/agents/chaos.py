from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.tools.chaos_tools import (
    dry_run_fault,
    inject_fault,
    inject_network_delay,
    inject_pod_kill,
    recover_fault,
)


class ChaosAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 카오스 엔지니어링 전문가입니다. "
            "Kubernetes 환경에서 의도적인 장애를 주입하여 시스템의 회복력을 검증하는 역할을 합니다.\n\n"
            "도구 선택 가이드:\n"
            "- dry_run_fault: 실험 시작 전 대상 리소스 존재 여부 검증 (실제 장애 없음)\n"
            "- inject_pod_kill: Pod 직접 삭제 장애 주입\n"
            "- inject_network_delay: 네트워크 지연 장애 주입 (delay_ms, duration_s 지정)\n"
            "- inject_fault: 위 두 가지를 fault_type 파라미터로 통합 호출\n"
            "- recover_fault: 주입된 장애 복구\n\n"
            "실행 결과를 명확하게 보고하고, DRY-RUN FAIL 시 즉시 실험을 중단하세요."
        )

    def get_tools(self) -> list:
        return [dry_run_fault, inject_pod_kill, inject_network_delay, inject_fault, recover_fault]
