# CLAUDE.md — Strands AIOps & Chaos Agent 프로젝트 명세

> **Claude에게**: 이 디렉토리에서는 웹 서비스 로직은 무시하고, 오직 **Strands SDK 기반의 멀티 에이전트 시스템(Python) 개발**에만 집중하세요.

## 1. 프로젝트 개요
- **목적**: Kubernetes 환경의 인프라 모니터링과 카오스 엔지니어링을 자동화하는 Multi-Agent 시스템 구축
- **핵심 프레임워크**: `strands-agents`, `strands-agents-tools` (Python)
- **AI 모델 및 환경**: **Amazon Bedrock** 환경의 Claude Sonnet (boto3 연동 필요)

## 2. 에이전트 설계 및 확장성

### 2-1. 에이전트 구성
향후 외부 툴(예: Chaos Mesh) 도입을 위해 모든 액션은 **추상화된 Tool 인터페이스**로 구현합니다.

1. **Admin Agent (오케스트레이터)** — `src/agents/admin.py`
   - `ExperimentState`를 통한 상태 기반(State-driven) 동적 워크플로우 제어
   - 메트릭 임계치 초과 시 즉시 롤백, 정상 시 복구 검증으로 자동 분기
   - 실험마다 `run()` 호출 시 상태 초기화(`state.reset()`)

2. **Planning Agent (실험 기획 담당)** — `src/agents/planning.py`
   - 사용자의 모호한 자연어 명령 → 구조화된 `ExperimentPlan` (JSON) 변환
   - Tool 없이 LLM만 사용 (순수 기획 역할)

3. **Chaos Agent (장애 주입 담당)** — `src/agents/chaos.py`
   - **(현재)** `kubectl` 기반 장애 주입: `inject_pod_kill`, `inject_network_delay`, `inject_fault`
   - **(미래 대비)** Chaos Mesh API로 교체 시 `FaultInjector` 구현체만 교체 (`KubectlFaultInjector` → `ChaosMeshFaultInjector`)
   - 주입 전 `dry_run_fault`로 대상 리소스 존재 검증

4. **Observability Agent (관측 담당)** — `src/agents/observability.py`
   - Prometheus 메트릭 조회 (CPU/Memory, 5xx 에러 등)
   - `check_metric_threshold`: EXCEEDED/OK 형태로 임계치 초과 여부 반환 → Admin의 롤백 판단 근거

5. **Infra Agent (복구/상태 확인 담당)** — `src/agents/infra.py`
   - K8s 클러스터 리소스 복구 여부 검증 (`kubectl get/describe` 활용)

### 2-2. 상태 관리 (`src/state.py`)
- `ExperimentStatus(Enum)`: `PENDING → PLANNING → DRY_RUN → INJECTING → OBSERVING → RECOVERING → COMPLETED | ABORTED`
- `ExperimentPlan(dataclass)`: 실험 대상 메타데이터 (namespace, target, fault_type, threshold 등)
- `ExperimentState(dataclass)`: 현재 상태 + 이벤트 타임라인 누적

## 3. 핵심 자동화 시나리오 (워크플로우)

Admin Agent가 아래 순서로 도구를 호출하며, **4번 결과에 따라 동적으로 분기**합니다:

1. **계획 수립** (`plan_experiment`): PlanningAgent가 자연어 → `ExperimentPlan` JSON 변환
2. **사전 검증** (`dry_run_experiment`): ChaosAgent가 대상 리소스 존재 여부 확인 (실패 시 즉시 중단)
3. **장애 주입** (`run_chaos_experiment`): ChaosAgent가 `abort_on_error_pct` 기준 설정 후 장애 실행
4. **메트릭 관측** (`observe_metrics`): ObservabilityAgent가 `check_metric_threshold` 호출
   - **EXCEEDED** → `rollback_experiment` 즉시 호출 → `ABORTED` 종료
   - **OK** → 5번으로 진행
5. **복구 검증** (`verify_recovery`): InfraAgent가 K8s 상태 확인 → `COMPLETED` 종료

## 4. 핵심 설계 원칙

- **Admin Tool은 클로저로 등록**: `get_tools()` 내부에서 `@tool` 데코레이터로 정의, `state_ref` 등 인스턴스 참조는 클로저로 캡처
- **`BedrockModel` 연동 코드 수정 금지**: `src/main.py`의 `create_bedrock_model()` 함수는 변경하지 않음
- **`strands-agents` SDK 구조 유지**: `Agent`, `BaseAgent` 래핑 패턴 그대로 사용
- **Tool 시그니처 변경 금지**: LLM이 호출하는 `inject_fault` / `recover_fault` 등 기존 @tool 시그니처는 변경 불가

## 5. 디렉토리 구조 가이드

```text
agent/
├── .venv/              (가상환경)
├── .env                (AWS 자격증명 등 환경변수)
├── CLAUDE.md           (Claude 지침서 - 루트에 위치)
├── src/
│   ├── main.py         (Bedrock Client 설정 및 에이전트 초기화)
│   ├── state.py        (ExperimentState, ExperimentStatus, ExperimentPlan)
│   ├── agents/
│   │   ├── base.py          (BaseAgent 추상 클래스)
│   │   ├── admin.py         (동적 오케스트레이터 — 상태 기반 워크플로우)
│   │   ├── planning.py      (자연어 → 실험 계획 변환)
│   │   ├── chaos.py
│   │   ├── observability.py
│   │   └── infra.py
│   └── tools/
│       ├── chaos_tools.py   (장애 주입 추상화: kubectl / ChaosMesh 전환 영역)
│       ├── k8s_tools.py     (순수 상태 조회용)
│       └── metrics_tools.py (Prometheus 쿼리 & 임계치 판단)
└── tests/
    ├── test_chaos_tools.py
    ├── test_k8s_tools.py
    ├── test_metrics_tools.py
    └── test_state.py
```
