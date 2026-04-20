import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.tools.chaos_tools import KubectlFaultInjector, inject_fault, recover_fault


class TestKubectlFaultInjector:
    def setup_method(self):
        self.injector = KubectlFaultInjector()

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_inject_pod_delete_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='pod "nginx-abc" deleted', stderr="")
        result = self.injector.inject("default", "nginx-abc", "pod_delete")
        assert "deleted" in result
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "delete" in cmd and "nginx-abc" in cmd

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_inject_pod_delete_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="pod not found")
        with pytest.raises(RuntimeError, match="kubectl delete failed"):
            self.injector.inject("default", "nginx-abc", "pod_delete")

    def test_inject_unknown_fault_type(self):
        with pytest.raises(ValueError, match="Unsupported fault_type"):
            self.injector.inject("default", "nginx-abc", "unknown_type")

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_recover_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="deployment.apps/nginx restarted", stderr=""
        )
        result = self.injector.recover("default", "nginx")
        assert "restarted" in result


class TestInjectFaultTool:
    @patch("src.tools.chaos_tools._get_injector")
    def test_inject_fault_calls_injector(self, mock_get):
        mock_injector = MagicMock()
        mock_injector.inject.return_value = "injected"
        mock_get.return_value = mock_injector
        # @tool 함수는 내부적으로 딕셔너리를 반환하므로 tool_use를 시뮬레이션
        result = inject_fault._tool_func(namespace="default", target_pod="nginx-abc", fault_type="pod_delete")
        assert result == "injected"
        mock_injector.inject.assert_called_once_with("default", "nginx-abc", "pod_delete")

    @patch("src.tools.chaos_tools._get_injector")
    def test_inject_fault_returns_error_string_on_exception(self, mock_get):
        mock_injector = MagicMock()
        mock_injector.inject.side_effect = RuntimeError("kubectl not found")
        mock_get.return_value = mock_injector
        result = inject_fault._tool_func(namespace="default", target_pod="nginx-abc", fault_type="pod_delete")
        assert "Error" in result
