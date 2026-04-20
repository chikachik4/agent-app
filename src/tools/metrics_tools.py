import logging
import os

import requests
from strands import tool

logger = logging.getLogger(__name__)

_PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


def _query(promql: str) -> dict:
    resp = requests.get(
        f"{_PROMETHEUS_URL}/api/v1/query",
        params={"query": promql},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@tool
def query_prometheus(promql: str, time_range_minutes: int = 5) -> str:
    """Prometheus에 PromQL 쿼리를 실행하고 결과를 반환합니다.

    Args:
        promql: 실행할 PromQL 쿼리 문자열
        time_range_minutes: 조회 범위(분), rate/increase 함수에서 사용
    """
    try:
        data = _query(promql)
        results = data.get("data", {}).get("result", [])
        if not results:
            return f"No data for query: {promql}"
        lines = []
        for r in results[:10]:
            metric = r.get("metric", {})
            value = r.get("value", [None, "N/A"])[1]
            lines.append(f"{metric} => {value}")
        return "\n".join(lines)
    except Exception as exc:
        logger.error("query_prometheus error: %s", exc)
        return f"Error querying Prometheus: {exc}"


@tool
def get_error_rate(namespace: str, service: str, time_range_minutes: int = 5) -> str:
    """서비스의 5xx 에러 비율(%)을 반환합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        service: 대상 서비스 이름
        time_range_minutes: 조회 범위(분)
    """
    window = f"{time_range_minutes}m"
    total_q = f'sum(rate(http_requests_total{{namespace="{namespace}",service="{service}"}}[{window}]))'
    error_q = f'sum(rate(http_requests_total{{namespace="{namespace}",service="{service}",status=~"5.."}}[{window}]))'
    try:
        total_data = _query(total_q)
        error_data = _query(error_q)
        total_val = float(total_data["data"]["result"][0]["value"][1]) if total_data["data"]["result"] else 0.0
        error_val = float(error_data["data"]["result"][0]["value"][1]) if error_data["data"]["result"] else 0.0
        rate_pct = (error_val / total_val * 100) if total_val > 0 else 0.0
        return (
            f"Service '{service}' in '{namespace}' — "
            f"5xx error rate: {rate_pct:.2f}% over last {time_range_minutes} min "
            f"(errors={error_val:.2f}/s, total={total_val:.2f}/s)"
        )
    except Exception as exc:
        logger.error("get_error_rate error: %s", exc)
        return f"Error fetching error rate: {exc}"


@tool
def get_pod_restart_count(namespace: str, pod_name: str) -> str:
    """Pod의 컨테이너 재시작 횟수를 반환합니다.

    Args:
        namespace: 대상 Kubernetes 네임스페이스
        pod_name: 조회할 Pod 이름
    """
    promql = (
        f'kube_pod_container_status_restarts_total'
        f'{{namespace="{namespace}",pod="{pod_name}"}}'
    )
    try:
        data = _query(promql)
        results = data.get("data", {}).get("result", [])
        if not results:
            return f"No restart data for pod '{pod_name}' in '{namespace}'."
        lines = []
        for r in results:
            container = r["metric"].get("container", "unknown")
            count = r["value"][1]
            lines.append(f"  {container}: {count} restarts")
        return f"Pod '{pod_name}' restart counts:\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("get_pod_restart_count error: %s", exc)
        return f"Error fetching restart count: {exc}"
