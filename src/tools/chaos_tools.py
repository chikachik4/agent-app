import logging
import os
import subprocess
from typing import Any, Protocol

import requests
from strands import tool

logger = logging.getLogger(__name__)


# ── Layer 2: 추상 인터페이스 ──────────────────────────────────────────────────

class FaultInjector(Protocol):
    def inject(self, namespace: str, target: str, fault_type: str, **kwargs: Any) -> str: ...
    def recover(self, namespace: str, target: str) -> str: ...


# ── Layer 3-A: kubectl 구현체 (현재 Phase 1~2) ───────────────────────────────

class KubectlFaultInjector:
    def inject(self, namespace: str, target: str, fault_type: str, **kwargs: Any) -> str:
        logger.info("kubectl inject: ns=%s target=%s type=%s", namespace, target, fault_type)
        if fault_type == "pod_delete":
            result = subprocess.run(
                ["kubectl", "delete", "pod", target, "-n", namespace, "--ignore-not-found=true"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"kubectl delete failed: {result.stderr}")
            return f"Pod '{target}' deleted from namespace '{namespace}'. {result.stdout.strip()}"

        if fault_type == "network_delay":
            delay_ms = kwargs.get("delay_ms", 500)
            # tc netem은 타겟 컨테이너 내부에서 실행돼야 하므로 exec으로 주입
            result = subprocess.run(
                [
                    "kubectl", "exec", target, "-n", namespace, "--",
                    "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
                    "delay", f"{delay_ms}ms",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"tc netem failed: {result.stderr}")
            return f"Network delay {delay_ms}ms injected into pod '{target}'."

        raise ValueError(f"Unsupported fault_type: '{fault_type}'. Use: pod_delete | network_delay")

    def recover(self, namespace: str, target: str) -> str:
        logger.info("kubectl recover: ns=%s target=%s", namespace, target)
        # deployment 이름으로 rollout restart 시도 (pod 이름이면 무시됨)
        result = subprocess.run(
            ["kubectl", "rollout", "restart", f"deployment/{target}", "-n", namespace],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"Recovery attempt info: {result.stderr.strip()}"
        return f"Deployment '{target}' in namespace '{namespace}' restarted. {result.stdout.strip()}"


# ── Layer 3-B: Chaos Mesh 구현체 (미래 Phase 3+) ─────────────────────────────

class ChaosMeshFaultInjector:
    def __init__(self) -> None:
        self._base_url = os.environ.get("CHAOS_MESH_URL", "http://chaos-mesh.chaos-testing:2333")
        self._active_experiment_ids: dict[str, str] = {}

    def inject(self, namespace: str, target: str, fault_type: str, **kwargs: Any) -> str:
        logger.info("ChaosMesh inject: ns=%s target=%s type=%s", namespace, target, fault_type)
        payload = self._build_payload(namespace, target, fault_type, **kwargs)
        resp = requests.post(f"{self._base_url}/api/v1/chaos-experiments", json=payload, timeout=30)
        resp.raise_for_status()
        experiment_id = resp.json().get("id", "unknown")
        self._active_experiment_ids[f"{namespace}/{target}"] = experiment_id
        return f"Chaos Mesh experiment '{experiment_id}' started (type={fault_type}) on '{target}'."

    def recover(self, namespace: str, target: str) -> str:
        logger.info("ChaosMesh recover: ns=%s target=%s", namespace, target)
        exp_id = self._active_experiment_ids.pop(f"{namespace}/{target}", None)
        if not exp_id:
            return f"No active Chaos Mesh experiment found for '{namespace}/{target}'."
        resp = requests.delete(f"{self._base_url}/api/v1/chaos-experiments/{exp_id}", timeout=30)
        resp.raise_for_status()
        return f"Chaos Mesh experiment '{exp_id}' deleted. Recovery complete."

    def _build_payload(self, namespace: str, target: str, fault_type: str, **kwargs: Any) -> dict:
        if fault_type == "pod_delete":
            return {
                "apiVersion": "chaos-mesh.org/v1alpha1",
                "kind": "PodChaos",
                "metadata": {"name": f"pod-delete-{target}", "namespace": namespace},
                "spec": {
                    "action": "pod-kill",
                    "selector": {"namespaces": [namespace], "labelSelectors": {"app": target}},
                    "mode": "one",
                },
            }
        if fault_type == "network_delay":
            delay_ms = kwargs.get("delay_ms", 500)
            return {
                "apiVersion": "chaos-mesh.org/v1alpha1",
                "kind": "NetworkChaos",
                "metadata": {"name": f"net-delay-{target}", "namespace": namespace},
                "spec": {
                    "action": "delay",
                    "selector": {"namespaces": [namespace], "labelSelectors": {"app": target}},
                    "mode": "all",
                    "delay": {"latency": f"{delay_ms}ms"},
                },
            }
        raise ValueError(f"Unsupported fault_type for Chaos Mesh: '{fault_type}'")


# ── 팩토리 함수 ───────────────────────────────────────────────────────────────

def _get_injector() -> FaultInjector:
    backend = os.environ.get("CHAOS_BACKEND", "kubectl")
    if backend == "chaos_mesh":
        return ChaosMeshFaultInjector()
    return KubectlFaultInjector()


# ── Layer 1: @tool 함수 (LLM 인터페이스 — 시그니처 변경 금지) ──────────────

@tool
def dry_run_fault(namespace: str, target: str, fault_type: str) -> str:
    """장애 주입 전 대상 리소스의 존재 여부를 사전 검증합니다. 실제 장애는 주입하지 않습니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        target: 검증할 Pod 또는 Deployment 이름
        fault_type: 검증할 장애 유형 — pod_delete | network_delay
    """
    try:
        pod_result = subprocess.run(
            ["kubectl", "get", "pod", target, "-n", namespace, "--ignore-not-found=true"],
            capture_output=True, text=True, timeout=30,
        )
        if pod_result.returncode == 0 and target in pod_result.stdout:
            return f"[DRY-RUN OK] Pod '{target}' exists in namespace '{namespace}'. Ready to inject '{fault_type}'."

        dep_result = subprocess.run(
            ["kubectl", "get", "deployment", target, "-n", namespace, "--ignore-not-found=true"],
            capture_output=True, text=True, timeout=30,
        )
        if dep_result.returncode == 0 and target in dep_result.stdout:
            return f"[DRY-RUN OK] Deployment '{target}' exists in namespace '{namespace}'. Ready to inject '{fault_type}'."

        return f"[DRY-RUN FAIL] Target '{target}' not found in namespace '{namespace}'. Aborting experiment."
    except Exception as exc:
        logger.error("dry_run_fault error: %s", exc)
        return f"Error during dry run: {exc}"


@tool
def inject_pod_kill(namespace: str, target_pod: str) -> str:
    """Pod를 강제 삭제하여 장애를 주입합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        target_pod: 삭제할 Pod 이름
    """
    try:
        result = subprocess.run(
            ["kubectl", "delete", "pod", target_pod, "-n", namespace, "--ignore-not-found=true"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"kubectl delete failed: {result.stderr}")
        return f"[POD_KILL] Pod '{target_pod}' deleted from namespace '{namespace}'. {result.stdout.strip()}"
    except Exception as exc:
        logger.error("inject_pod_kill error: %s", exc)
        return f"Error: {exc}"


@tool
def inject_network_delay(namespace: str, target_pod: str, delay_ms: int = 500, duration_s: int = 60) -> str:
    """Pod에 네트워크 지연을 주입합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        target_pod: 대상 Pod 이름
        delay_ms: 지연 시간 (밀리초, 기본값 500)
        duration_s: 지연 유지 시간 (초, 기본값 60, 0이면 수동 복구 필요)
    """
    try:
        result = subprocess.run(
            [
                "kubectl", "exec", target_pod, "-n", namespace, "--",
                "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
                "delay", f"{delay_ms}ms",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"tc netem failed: {result.stderr}")
        msg = f"[NET_DELAY] {delay_ms}ms delay injected into pod '{target_pod}' in namespace '{namespace}'."
        if duration_s > 0:
            msg += f" Duration: {duration_s}s."
        return msg
    except Exception as exc:
        logger.error("inject_network_delay error: %s", exc)
        return f"Error: {exc}"


@tool
def inject_fault(namespace: str, target_pod: str, fault_type: str) -> str:
    """타겟 Pod에 장애를 주입합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        target_pod: 대상 Pod 또는 Deployment 이름
        fault_type: 장애 유형 — pod_delete | network_delay
    """
    try:
        return _get_injector().inject(namespace, target_pod, fault_type)
    except Exception as exc:
        logger.error("inject_fault error: %s", exc)
        return f"Error injecting fault: {exc}"


@tool
def recover_fault(namespace: str, target_pod: str) -> str:
    """주입된 장애를 복구하고 결과를 반환합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        target_pod: 복구할 Pod 또는 Deployment 이름
    """
    try:
        return _get_injector().recover(namespace, target_pod)
    except Exception as exc:
        logger.error("recover_fault error: %s", exc)
        return f"Error recovering fault: {exc}"
