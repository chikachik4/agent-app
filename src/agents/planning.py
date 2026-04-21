from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent


class PlanningAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 카오스 엔지니어링 실험 기획 전문가입니다. "
            "사용자의 자연어 명령을 분석하여 구체적인 카오스 실험 계획을 JSON 형식으로만 출력합니다.\n\n"
            "반드시 아래 JSON 스키마를 준수하세요:\n"
            "{\n"
            '  "namespace": "string",\n'
            '  "target": "string (Pod 또는 Deployment 이름)",\n'
            '  "fault_type": "pod_delete | network_delay",\n'
            '  "service": "string (Prometheus 메트릭 조회용 서비스 이름)",\n'
            '  "deployment_name": "string (복구 검증용 Deployment 이름)",\n'
            '  "error_threshold_pct": number (기본값 10.0),\n'
            '  "observation_minutes": number (기본값 5)\n'
            "}\n\n"
            "JSON 이외의 텍스트는 절대 출력하지 마세요. "
            "명령에서 명시되지 않은 필드는 합리적인 기본값으로 추론하세요. "
            "namespace가 명시되지 않으면 'default'로 가정하세요."
        )

    def get_tools(self) -> list:
        return []
