from src.state import ExperimentPlan, ExperimentState, ExperimentStatus


class TestExperimentState:
    def test_initial_status_is_pending(self):
        state = ExperimentState()
        assert state.status == ExperimentStatus.PENDING
        assert state.plan is None
        assert state.events == []

    def test_transition_updates_status(self):
        state = ExperimentState()
        state.transition(ExperimentStatus.PLANNING, "test message")
        assert state.status == ExperimentStatus.PLANNING

    def test_transition_appends_event_with_status_label(self):
        state = ExperimentState()
        state.transition(ExperimentStatus.INJECTING, "주입 시작")
        assert any("INJECTING" in e for e in state.events)
        assert any("주입 시작" in e for e in state.events)

    def test_abort_sets_aborted_status(self):
        state = ExperimentState()
        state.abort("threshold exceeded")
        assert state.status == ExperimentStatus.ABORTED

    def test_abort_logs_abort_prefix(self):
        state = ExperimentState()
        state.abort("threshold exceeded")
        assert any("ABORT" in e for e in state.events)

    def test_timeline_returns_all_events_in_order(self):
        state = ExperimentState()
        state.transition(ExperimentStatus.PLANNING, "planning")
        state.transition(ExperimentStatus.INJECTING, "injecting")
        timeline = state.timeline()
        assert "PLANNING" in timeline
        assert "INJECTING" in timeline
        assert timeline.index("PLANNING") < timeline.index("INJECTING")

    def test_timeline_empty_returns_sentinel(self):
        state = ExperimentState()
        assert "(no events)" in state.timeline()

    def test_reset_clears_all_fields(self):
        state = ExperimentState()
        state.transition(ExperimentStatus.INJECTING, "before reset")
        state.plan = ExperimentPlan(
            namespace="default", target="nginx", fault_type="pod_delete",
        )
        state.reset()
        assert state.status == ExperimentStatus.PENDING
        assert state.plan is None
        assert state.events == []

    def test_multiple_transitions_accumulate_events(self):
        state = ExperimentState()
        for status in [
            ExperimentStatus.PLANNING,
            ExperimentStatus.DRY_RUN,
            ExperimentStatus.INJECTING,
            ExperimentStatus.OBSERVING,
        ]:
            state.transition(status)
        assert len(state.events) == 4
        assert state.status == ExperimentStatus.OBSERVING
