import json
import logging
import re
from datetime import datetime

from strands import tool
from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.agents.chaos import ChaosAgent
from src.agents.infra import InfraAgent
from src.agents.observability import ObservabilityAgent
from src.agents.planning import PlanningAgent
from src.state import ExperimentPlan, ExperimentState, ExperimentStatus

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON found in planning response: {text[:200]}")


class AdminAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        self._chaos = ChaosAgent(model)
        self._obs = ObservabilityAgent(model)
        self._infra = InfraAgent(model)
        self._planning = PlanningAgent(model)
        self._state = ExperimentState()
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 AIOps 오케스트레이터입니다. 카오스 실험을 상태 기반으로 동적 제어합니다.\n\n"
            "워크플로우 (순서대로 실행, 결과에 따라 동적 분기):\n"
            "1. plan_experiment: 자연어 명령 → 구조화된 실험 계획 수립\n"
            "2. dry_run_experiment: 대상 리소스 존재 여부 사전 검증\n"
            "   - 'DRY-RUN FAIL' 포함 시 → 즉시 중단하고 이유를 보고\n"
            "3. run_chaos_experiment: 장애 주입 (abort_on_error_pct로 긴급 중단 기준 설정)\n"
            "4. observe_metrics: 메트릭 관측 및 임계치 확인\n"
            "   - 'EXCEEDED' 포함 시 → rollback_experiment 즉시 호출 후 ABORTED 보고\n"
            "   - 'OK' 이면 → 5번으로 진행\n"
            "5. verify_recovery: 자연 복구 완료 여부 확인 후 최종 보고\n\n"
            "최종 결과는 실험 타임라인과 함께 성공/실패/중단 여부를 명확히 보고하세요."
        )

    def get_tools(self) -> list:
        state_ref = self._state
        chaos_ref = self._chaos
        obs_ref = self._obs
        infra_ref = self._infra
        planning_ref = self._planning

        @tool
        def plan_experiment(user_command: str) -> str:
            """PlanningAgent를 호출하여 자연어 명령을 구조화된 실험 계획으로 변환합니다.

            Args:
                user_command: 사용자의 자연어 카오스 실험 명령
            """
            logger.info("[Admin] plan_experiment: %s", user_command)
            state_ref.transition(ExperimentStatus.PLANNING, f"입력 명령: {user_command}")
            plan_text = planning_ref.run(user_command)
            try:
                plan_data = _extract_json(plan_text)
                state_ref.plan = ExperimentPlan(**plan_data)
                return f"실험 계획 수립 완료:\n{json.dumps(plan_data, ensure_ascii=False, indent=2)}"
            except Exception as exc:
                logger.error("plan_experiment parse error: %s", exc)
                return f"계획 파싱 실패: {exc}\n원본 응답: {plan_text}"

        @tool
        def dry_run_experiment(namespace: str, target: str, fault_type: str) -> str:
            """장애 주입 전 대상 리소스 존재 여부를 Chaos Agent에게 검증 요청합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                target: 검증할 Pod 또는 Deployment 이름
                fault_type: 검증할 장애 유형 — pod_delete | network_delay
            """
            logger.info("[Admin] dry_run_experiment: %s/%s", namespace, target)
            state_ref.transition(ExperimentStatus.DRY_RUN, f"사전 검증: {namespace}/{target}")
            prompt = (
                f"'{namespace}' 네임스페이스에서 '{target}' 리소스가 존재하는지 "
                f"dry_run_fault 도구로 검증해줘. fault_type은 '{fault_type}'이야."
            )
            return chaos_ref.run(prompt)

        @tool
        def run_chaos_experiment(
            namespace: str,
            target_pod: str,
            fault_type: str,
            abort_on_error_pct: float = 20.0,
            duration_s: int = 0,
        ) -> str:
            """Chaos Agent에게 장애 주입을 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                target_pod: 장애를 주입할 Pod 또는 Deployment 이름
                fault_type: 장애 유형 — pod_delete | network_delay
                abort_on_error_pct: 이 에러율(%)을 초과하면 즉시 롤백 (기본값 20.0)
                duration_s: 장애 유지 시간(초), 0이면 수동 복구 (network_delay에만 해당)
            """
            logger.info(
                "[Admin] run_chaos_experiment: %s/%s (%s) abort_at=%.1f%%",
                namespace, target_pod, fault_type, abort_on_error_pct,
            )
            state_ref.transition(
                ExperimentStatus.INJECTING,
                f"{namespace}/{target_pod} ({fault_type}), abort_on_error_pct={abort_on_error_pct}%",
            )
            if fault_type == "network_delay" and duration_s > 0:
                prompt = (
                    f"'{namespace}' 네임스페이스의 '{target_pod}'에 "
                    f"inject_network_delay 도구로 네트워크 지연 장애를 주입해줘. "
                    f"duration_s={duration_s}으로 설정해줘."
                )
            else:
                prompt = (
                    f"'{namespace}' 네임스페이스의 '{target_pod}'에 '{fault_type}' 장애를 주입해줘."
                )
            return chaos_ref.run(prompt)

        @tool
        def observe_metrics(
            namespace: str,
            service: str,
            time_range_minutes: int = 5,
            error_threshold_pct: float = 10.0,
        ) -> str:
            """Observability Agent에게 메트릭 관측 및 임계치 확인을 지시합니다.
            결과에 'EXCEEDED'가 포함되면 즉시 rollback_experiment를 호출해야 합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                service: 관측할 서비스 이름
                time_range_minutes: 조회 범위(분)
                error_threshold_pct: 롤백 기준 에러율 임계치(%), 기본값 10.0
            """
            logger.info("[Admin] observe_metrics: %s/%s threshold=%.1f%%", namespace, service, error_threshold_pct)
            state_ref.transition(
                ExperimentStatus.OBSERVING,
                f"{namespace}/{service}, threshold={error_threshold_pct}%",
            )
            prompt = (
                f"'{namespace}' 네임스페이스의 '{service}' 서비스에 대해 "
                f"최근 {time_range_minutes}분간 에러율을 확인하고, "
                f"check_metric_threshold 도구로 임계치 {error_threshold_pct}%를 기준으로 "
                "EXCEEDED 또는 OK 여부를 반드시 포함해서 보고해줘."
            )
            result = obs_ref.run(prompt)
            if "EXCEEDED" in result:
                state_ref.transition(
                    ExperimentStatus.RECOVERING,
                    f"임계치 초과 감지 — 즉시 롤백 필요 (threshold={error_threshold_pct}%)",
                )
            return result

        @tool
        def rollback_experiment(namespace: str, target: str) -> str:
            """임계치 초과 또는 이상 징후 발생 시 Chaos Agent에게 즉시 장애 복구를 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                target: 복구할 Pod 또는 Deployment 이름
            """
            logger.info("[Admin] rollback_experiment: %s/%s", namespace, target)
            prompt = (
                f"'{namespace}' 네임스페이스의 '{target}'에 주입된 장애를 "
                "recover_fault 도구로 즉시 복구해줘."
            )
            result = chaos_ref.run(prompt)
            state_ref.abort(f"임계치 초과로 조기 종료 — {namespace}/{target} 복구 완료")
            return f"{result}\n\n--- 실험 타임라인 (조기 중단) ---\n{state_ref.timeline()}"

        @tool
        def verify_recovery(namespace: str, deployment_name: str) -> str:
            """Infra Agent에게 자연 복구 완료 여부 확인을 지시합니다.

            Args:
                namespace: 대상 Kubernetes 네임스페이스
                deployment_name: 복구 여부를 확인할 Deployment 이름
            """
            logger.info("[Admin] verify_recovery: %s/%s", namespace, deployment_name)
            state_ref.transition(ExperimentStatus.RECOVERING, f"{namespace}/{deployment_name} 복구 검증")
            prompt = (
                f"'{namespace}' 네임스페이스의 '{deployment_name}' Deployment가 "
                "완전히 복구되었는지 확인해줘. "
                "모든 Pod가 Running 상태이고 desired replicas를 충족하는지 검증해줘."
            )
            result = infra_ref.run(prompt)
            state_ref.transition(ExperimentStatus.COMPLETED, "복구 검증 완료")
            return f"{result}\n\n--- 실험 타임라인 ---\n{state_ref.timeline()}"

        return [
            plan_experiment,
            dry_run_experiment,
            run_chaos_experiment,
            observe_metrics,
            rollback_experiment,
            verify_recovery,
        ]

    def run(self, prompt: str) -> str:
        self._state.reset()
        self._state.started_at = datetime.now()
        return super().run(prompt)
