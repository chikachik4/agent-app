import json
import logging
import subprocess

from strands import tool

logger = logging.getLogger(__name__)


def _kubectl(args: list[str]) -> tuple[str, str, int]:
    result = subprocess.run(
        ["kubectl", *args],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout, result.stderr, result.returncode


@tool
def get_pods(namespace: str, label_selector: str = "") -> str:
    """네임스페이스의 Pod 목록과 상태를 반환합니다.

    Args:
        namespace: 조회할 Kubernetes 네임스페이스
        label_selector: 필터링할 레이블 셀렉터 (예: "app=nginx"), 빈 문자열이면 전체 조회
    """
    cmd = ["get", "pods", "-n", namespace, "-o", "json"]
    if label_selector:
        cmd += ["-l", label_selector]
    stdout, stderr, rc = _kubectl(cmd)
    if rc != 0:
        logger.error("get_pods failed: %s", stderr)
        return f"Error: {stderr}"
    pods = json.loads(stdout).get("items", [])
    summary = []
    for p in pods:
        name = p["metadata"]["name"]
        phase = p["status"].get("phase", "Unknown")
        ready_conds = [c for c in p["status"].get("conditions", []) if c["type"] == "Ready"]
        ready = ready_conds[0]["status"] if ready_conds else "Unknown"
        summary.append(f"{name}: phase={phase}, ready={ready}")
    return "\n".join(summary) if summary else f"No pods found in namespace '{namespace}'."


@tool
def get_deployment_status(namespace: str, deployment_name: str) -> str:
    """Deployment의 Ready/Available 레플리카 수를 반환합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        deployment_name: 조회할 Deployment 이름
    """
    stdout, stderr, rc = _kubectl(
        ["get", "deployment", deployment_name, "-n", namespace, "-o", "json"]
    )
    if rc != 0:
        logger.error("get_deployment_status failed: %s", stderr)
        return f"Error: {stderr}"
    spec = json.loads(stdout)
    status = spec.get("status", {})
    desired = spec.get("spec", {}).get("replicas", "?")
    ready = status.get("readyReplicas", 0)
    available = status.get("availableReplicas", 0)
    return (
        f"Deployment '{deployment_name}' in '{namespace}': "
        f"desired={desired}, ready={ready}, available={available}"
    )


@tool
def describe_pod(namespace: str, pod_name: str) -> str:
    """Pod의 상세 정보(이벤트 포함)를 반환합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        pod_name: 조회할 Pod 이름
    """
    stdout, stderr, rc = _kubectl(["describe", "pod", pod_name, "-n", namespace])
    if rc != 0:
        logger.error("describe_pod failed: %s", stderr)
        return f"Error: {stderr}"
    # 이벤트 섹션만 추출해 LLM 컨텍스트를 줄임
    lines = stdout.splitlines()
    event_start = next((i for i, l in enumerate(lines) if l.startswith("Events:")), None)
    if event_start is not None:
        return "\n".join(lines[event_start:])
    return stdout[:3000]
