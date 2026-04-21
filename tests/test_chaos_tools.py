import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.tools.chaos_tools import (
    KubectlFaultInjector,
    dry_run_fault,
    inject_fault,
    inject_network_delay,
    inject_pod_kill,
    recover_fault,
)


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


class TestDryRunFault:
    @patch("src.tools.chaos_tools.subprocess.run")
    def test_pod_exists_returns_ok(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="nginx-abc   Running", stderr="")
        result = dry_run_fault._tool_func(namespace="default", target="nginx-abc", fault_type="pod_delete")
        assert "DRY-RUN OK" in result
        assert "Pod" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_deployment_exists_returns_ok(self, mock_run):
        # First call (pod check) returns empty, second call (deployment check) returns hit
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="nginx   1/1", stderr=""),
        ]
        result = dry_run_fault._tool_func(namespace="default", target="nginx", fault_type="pod_delete")
        assert "DRY-RUN OK" in result
        assert "Deployment" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_target_not_found_returns_fail(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = dry_run_fault._tool_func(namespace="default", target="missing-pod", fault_type="pod_delete")
        assert "DRY-RUN FAIL" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_subprocess_exception_returns_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("kubectl not found")
        result = dry_run_fault._tool_func(namespace="default", target="nginx-abc", fault_type="pod_delete")
        assert "Error" in result


class TestInjectPodKill:
    @patch("src.tools.chaos_tools.subprocess.run")
    def test_success_returns_pod_kill_label(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='pod "nginx-abc" deleted', stderr="")
        result = inject_pod_kill._tool_func(namespace="default", target_pod="nginx-abc")
        assert "POD_KILL" in result
        assert "deleted" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_failure_returns_error_string(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="forbidden")
        result = inject_pod_kill._tool_func(namespace="default", target_pod="nginx-abc")
        assert "Error" in result


class TestInjectNetworkDelay:
    @patch("src.tools.chaos_tools.subprocess.run")
    def test_success_returns_net_delay_label(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = inject_network_delay._tool_func(
            namespace="default", target_pod="nginx-abc", delay_ms=200, duration_s=30,
        )
        assert "NET_DELAY" in result
        assert "200ms" in result
        assert "30s" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_default_delay_ms_is_500(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = inject_network_delay._tool_func(namespace="default", target_pod="nginx-abc")
        assert "500ms" in result

    @patch("src.tools.chaos_tools.subprocess.run")
    def test_failure_returns_error_string(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="tc not found")
        result = inject_network_delay._tool_func(namespace="default", target_pod="nginx-abc", delay_ms=200)
        assert "Error" in result
