import logging

from strands import tool
from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.agents.chaos import ChaosAgent
from src.agents.infra import InfraAgent
from src.agents.observability import ObservabilityAgent

logger = logging.getLogger(__name__)


class AdminAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        self._chaos = ChaosAgent(model)
        self._obs = ObservabilityAgent(model)
        self._infra = InfraAgent(model)
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 AIOps 오케스트레이터입니다. "
            "사용자의 카오스 엔지니어링 요청을 분석하고 세 가지 전문 에이전트를 순서대로 호출하여 "
            "완전한 카오스 실험을 진행합니다:\n"
            "1. run_chaos_experiment: 장애 주입 (Chaos Agent 호출)\n"
            "2. observe_metrics: 메트릭 관측 (Observability Agent 호출)\n"
            "3. verify_recovery: 복구 상태 확인 (Infra Agent 호출)\n\n"
            "실험이 완료되면 타임라인 형식으로 전체 결과를 요약하여 보고하세요. "
            "각 단계의 결과를 명확히 구분하고, 복구 성공/실패 여부를 최종 결론으로 제시하세요."
        )

    def get_tools(self) -> list:
        # AdminAgent 인스턴스 메서드를 @tool로 등록하기 위해 클로저 사용
        chaos_ref = self._chaos
        obs_ref = self._obs
        infra_ref = self._infra

        @tool
        def run_chaos_experiment(namespace: str, target_pod: str, fault_type: str) -> str:
            """Chaos Agent에게 장애 주입을 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                target_pod: 장애를 주입할 Pod 또는 Deployment 이름
                fault_type: 장애 유형 — pod_delete | network_delay
            """
            logger.info("[Admin] run_chaos_experiment: %s/%s (%s)", namespace, target_pod, fault_type)
            prompt = f"'{namespace}' 네임스페이스의 '{target_pod}'에 '{fault_type}' 장애를 주입해줘."
            return chaos_ref.run(prompt)

        @tool
        def observe_metrics(namespace: str, service: str, time_range_minutes: int = 5) -> str:
            """Observability Agent에게 메트릭 관측을 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                service: 관측할 서비스 이름
                time_range_minutes: 조회 범위(분)
            """
            logger.info("[Admin] observe_metrics: %s/%s", namespace, service)
            prompt = (
                f"'{namespace}' 네임스페이스의 '{service}' 서비스에 대해 "
                f"최근 {time_range_minutes}분간 에러율과 트래픽 변화를 확인해줘."
            )
            return obs_ref.run(prompt)

        @tool
        def verify_recovery(namespace: str, deployment_name: str) -> str:
            """Infra Agent에게 복구 상태 확인을 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                deployment_name: 복구 여부를 확인할 Deployment 이름
            """
            logger.info("[Admin] verify_recovery: %s/%s", namespace, deployment_name)
            prompt = (
                f"'{namespace}' 네임스페이스의 '{deployment_name}' Deployment가 "
                "완전히 복구되었는지 확인해줘. "
                "모든 Pod가 Running 상태이고 desired replicas를 충족하는지 검증해줘."
            )
            return infra_ref.run(prompt)

        return [run_chaos_experiment, observe_metrics, verify_recovery]
