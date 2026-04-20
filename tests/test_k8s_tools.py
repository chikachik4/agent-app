import json
from unittest.mock import patch

import pytest

from src.tools.k8s_tools import describe_pod, get_deployment_status, get_pods


MOCK_PODS_JSON = json.dumps({
    "items": [
        {
            "metadata": {"name": "nginx-abc"},
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "True"}],
            },
        }
    ]
})

MOCK_DEPLOYMENT_JSON = json.dumps({
    "spec": {"replicas": 3},
    "status": {"readyReplicas": 3, "availableReplicas": 3},
})


class TestGetPods:
    @patch("src.tools.k8s_tools.subprocess.run")
    def test_returns_pod_summary(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": MOCK_PODS_JSON, "stderr": "", "returncode": 0})()
        result = get_pods._tool_func(namespace="default")
        assert "nginx-abc" in result
        assert "Running" in result

    @patch("src.tools.k8s_tools.subprocess.run")
    def test_returns_error_on_failure(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": "", "stderr": "forbidden", "returncode": 1})()
        result = get_pods._tool_func(namespace="default")
        assert "Error" in result

    @patch("src.tools.k8s_tools.subprocess.run")
    def test_empty_namespace_returns_no_pods_message(self, mock_run):
        mock_run.return_value = type("R", (), {
            "stdout": json.dumps({"items": []}), "stderr": "", "returncode": 0
        })()
        result = get_pods._tool_func(namespace="empty-ns")
        assert "No pods found" in result


class TestGetDeploymentStatus:
    @patch("src.tools.k8s_tools.subprocess.run")
    def test_returns_replica_counts(self, mock_run):
        mock_run.return_value = type("R", (), {
            "stdout": MOCK_DEPLOYMENT_JSON, "stderr": "", "returncode": 0
        })()
        result = get_deployment_status._tool_func(namespace="default", deployment_name="nginx")
        assert "desired=3" in result
        assert "ready=3" in result


class TestDescribePod:
    @patch("src.tools.k8s_tools.subprocess.run")
    def test_returns_events_section(self, mock_run):
        stdout = "Name: nginx-abc\nNamespace: default\n\nEvents:\n  Type    Reason   Message\n  Normal  Pulled   Successfully pulled image"
        mock_run.return_value = type("R", (), {"stdout": stdout, "stderr": "", "returncode": 0})()
        result = describe_pod._tool_func(namespace="default", pod_name="nginx-abc")
        assert "Events:" in result
