from strands.models.bedrock import BedrockModel

from src.agents.base import BaseAgent
from src.tools.k8s_tools import describe_pod, get_deployment_status, get_pods


class InfraAgent(BaseAgent):
    def __init__(self, model: BedrockModel) -> None:
        super().__init__(model)

    @property
    def system_prompt(self) -> str:
        return (
            "당신은 Kubernetes 인프라 전문가입니다. "
            "클러스터의 리소스 상태를 조회하고 장애 복구 여부를 검증합니다. "
            "Pod가 Running 상태인지, ReplicaSet이 올바른 수의 Pod를 유지하는지, "
            "Deployment가 정상적으로 Rolling Update를 완료했는지 확인하세요. "
            "조회 결과를 구체적인 수치와 상태값으로 보고하세요."
        )

    def get_tools(self) -> list:
        return [get_pods, get_deployment_status, describe_pod]
