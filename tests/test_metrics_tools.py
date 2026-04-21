from unittest.mock import patch

from src.tools.metrics_tools import check_metric_threshold


def _make_result(value: float) -> dict:
    return {"data": {"result": [{"metric": {}, "value": [0, str(value)]}]}}


def _make_empty() -> dict:
    return {"data": {"result": []}}


class TestCheckMetricThreshold:
    @patch("src.tools.metrics_tools._query")
    def test_error_rate_exceeded(self, mock_query):
        # total=100 req/s, error=15 req/s → 15% > threshold 10%
        mock_query.side_effect = [_make_result(100.0), _make_result(15.0)]
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="error_rate", threshold_pct=10.0,
        )
        assert "EXCEEDED" in result
        assert "15.00%" in result

    @patch("src.tools.metrics_tools._query")
    def test_error_rate_ok(self, mock_query):
        # total=100 req/s, error=5 req/s → 5% <= threshold 10%
        mock_query.side_effect = [_make_result(100.0), _make_result(5.0)]
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="error_rate", threshold_pct=10.0,
        )
        assert "OK" in result
        assert "5.00%" in result

    @patch("src.tools.metrics_tools._query")
    def test_error_rate_zero_total_returns_ok(self, mock_query):
        # total=0 → division-by-zero guard, actual_pct=0.0
        mock_query.side_effect = [_make_empty(), _make_empty()]
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="error_rate", threshold_pct=10.0,
        )
        assert "OK" in result

    @patch("src.tools.metrics_tools._query")
    def test_cpu_usage_exceeded(self, mock_query):
        mock_query.return_value = _make_result(85.0)
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="cpu_usage", threshold_pct=80.0,
        )
        assert "EXCEEDED" in result

    @patch("src.tools.metrics_tools._query")
    def test_memory_usage_ok(self, mock_query):
        mock_query.return_value = _make_result(60.0)
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="memory_usage", threshold_pct=70.0,
        )
        assert "OK" in result

    def test_unsupported_metric_type_returns_error_message(self):
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="latency_p99", threshold_pct=500.0,
        )
        assert "Unsupported" in result

    @patch("src.tools.metrics_tools._query")
    def test_query_exception_returns_error_string(self, mock_query):
        mock_query.side_effect = ConnectionError("prometheus unreachable")
        result = check_metric_threshold._tool_func(
            namespace="default", service="nginx",
            metric_type="error_rate", threshold_pct=10.0,
        )
        assert "Error" in result
