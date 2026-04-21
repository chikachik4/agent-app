# Strands AIOps & Chaos Multi-Agent System

Kubernetes 환경의 인프라 모니터링과 카오스 엔지니어링을 자동화하는 **멀티 에이전트 시스템**입니다.  
[Strands Agents SDK](https://github.com/strands-agents/sdk-python) 기반으로 구축되었으며, **Amazon Bedrock**을 통해 Claude Sonnet 모델을 호출합니다.

---

## 주요 기능

- **자연어 명령 한 줄**로 카오스 실험 전 과정 자동 실행
- **상태 기반(State-driven) 동적 워크플로우** — 메트릭 임계치 초과 시 즉시 롤백, 정상 시 복구 검증으로 자동 분기
- 실험 전 **dry-run 사전 검증** — 대상 리소스 존재 여부 확인 후 장애 주입
- `CHAOS_BACKEND` 환경변수 하나로 **kubectl ↔ Chaos Mesh 백엔드 교체** 가능 (코드 수정 불필요)

---

## 아키텍처

```
User (자연어 명령)
        │
        ▼
┌──────────────────────────────────────────────┐
│                 Admin Agent                   │
│  ExperimentState (PENDING→...→COMPLETED)      │
│                                               │
│  1. plan_experiment ──────────► PlanningAgent │
│     └─ 자연어 → ExperimentPlan (JSON)         │
│                                               │
│  2. dry_run_experiment ───────► ChaosAgent   │
│     └─ 리소스 존재 검증 (장애 주입 없음)       │
│        DRY-RUN FAIL → 즉시 중단               │
│                                               │
│  3. run_chaos_experiment ─────► ChaosAgent   │
│     (abort_on_error_pct 설정)                 │
│                                               │
│  4. observe_metrics ──────────► ObsAgent     │
│     └─ check_metric_threshold 결과 평가       │
│        EXCEEDED → rollback_experiment (중단)  │
│        OK → 5번으로 진행                      │
│                                               │
│  5. verify_recovery ──────────► InfraAgent   │
│     └─ 복구 완료 → 타임라인 리포트            │
└──────────────────────────────────────────────┘
```

### 상태 전이

```
PENDING → PLANNING → DRY_RUN → INJECTING → OBSERVING
                                                │
                                    ┌───────────┴───────────┐
                                 EXCEEDED                   OK
                                    │                       │
                               RECOVERING              RECOVERING
                                    │                       │
                                ABORTED               COMPLETED
```

### 에이전트 역할

| 에이전트 | 역할 | 주요 도구 |
|---|---|---|
| **Admin** | 동적 오케스트레이션 & 상태 관리 | `plan_experiment`, `dry_run_experiment`, `run_chaos_experiment`, `observe_metrics`, `rollback_experiment`, `verify_recovery` |
| **Planning** | 자연어 → 구조화된 실험 계획(JSON) 변환 | (LLM only) |
| **Chaos** | 장애 주입 & 복구 | `dry_run_fault`, `inject_pod_kill`, `inject_network_delay`, `inject_fault`, `recover_fault` |
| **Observability** | 메트릭 관측 & 임계치 판단 | `check_metric_threshold`, `get_error_rate`, `query_prometheus`, `get_pod_restart_count` |
| **Infra** | 복구 상태 검증 | `get_pods`, `get_deployment_status`, `describe_pod` |

---

## 디렉토리 구조

```
agent/
├── .env                        # AWS 자격증명 및 환경변수 (git 제외)
├── requirements.txt
├── src/
│   ├── main.py                 # 진입점 — Bedrock 초기화 & 대화 루프
│   ├── state.py                # ExperimentState, ExperimentStatus, ExperimentPlan
│   ├── agents/
│   │   ├── base.py             # BaseAgent 추상 클래스
│   │   ├── admin.py            # 동적 오케스트레이터 (상태 기반 워크플로우)
│   │   ├── planning.py         # 자연어 → 실험 계획 변환
│   │   ├── chaos.py
│   │   ├── observability.py
│   │   └── infra.py
│   └── tools/
│       ├── chaos_tools.py      # 장애 주입 추상화 레이어 (kubectl / Chaos Mesh)
│       ├── k8s_tools.py        # K8s 상태 조회
│       └── metrics_tools.py    # Prometheus 쿼리 & 임계치 판단
└── tests/
    ├── test_chaos_tools.py
    ├── test_k8s_tools.py
    ├── test_metrics_tools.py
    └── test_state.py
```

---

## 시작하기

### 사전 요구사항

- Python 3.10+
- `kubectl` 설치 및 클러스터 접근 가능
- AWS 계정 및 Bedrock Claude Sonnet 모델 접근 권한
- (선택) Prometheus 엔드포인트

### 설치

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 환경변수 설정

`.env` 파일을 열어 필요한 값을 채웁니다:

```env
# AWS Credentials (선택 — EC2 IAM Role 환경에서는 불필요)
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key

# Kubernetes (선택 — 미설정 시 ~/.kube/config 자동 사용)
# KUBECONFIG=/path/to/kubeconfig

# Prometheus (선택 — 미설정 시 Observability Agent 비활성)
PROMETHEUS_URL=http://localhost:9090

# Chaos Backend: "kubectl" (기본값) 또는 "chaos_mesh"
CHAOS_BACKEND=kubectl
```

> EC2 인스턴스에 IAM Role이 부여되어 있거나 로컬에 `aws configure`가 설정된 경우, AWS 크리덴셜 항목은 비워두어도 됩니다.

### 실행

```bash
python src/main.py
```

```
=== Strands AIOps & Chaos Multi-Agent System ===
예시: 'default 네임스페이스의 nginx-pod에 카오스 테스트 시작해'

User> default 네임스페이스의 nginx-deployment에 카오스 테스트 시작해

Admin> [실험 타임라인]
  [10:01:00][PLANNING]   입력 명령: default 네임스페이스의 nginx-deployment에 카오스 테스트 시작해
  [10:01:02][DRY_RUN]    사전 검증: default/nginx-deployment → DRY-RUN OK
  [10:01:03][INJECTING]  default/nginx-deployment (pod_delete), abort_on_error_pct=20.0%
  [10:01:05][OBSERVING]  default/nginx, threshold=10.0%  → OK: error_rate=2.1%
  [10:01:10][RECOVERING] default/nginx-deployment 복구 검증
  [10:01:12][COMPLETED]  복구 검증 완료

  결론: desired=3 / ready=3 — Auto-healing 정상 동작 확인
```

---

## 동적 롤백 시나리오

임계치를 초과하면 즉시 롤백 후 `ABORTED`로 종료됩니다:

```
User> default 네임스페이스의 api-server에 network_delay 카오스 테스트 시작해

Admin> [실험 타임라인]
  [10:05:00][PLANNING]   입력 명령 분석 완료
  [10:05:02][DRY_RUN]    사전 검증: default/api-server → DRY-RUN OK
  [10:05:03][INJECTING]  default/api-server (network_delay)
  [10:05:08][OBSERVING]  임계치 확인 → EXCEEDED: error_rate=38.5% > threshold=10.0%
  [10:05:09][RECOVERING] 임계치 초과 감지 — 즉시 롤백 필요
  [10:05:10][ABORTED]    ABORT: 임계치 초과로 조기 종료 — 복구 완료

  결론: 임계치 초과(38.5%)로 실험 조기 중단. 장애 복구 완료.
```

---

## 카오스 백엔드 전환 (kubectl → Chaos Mesh)

코드를 수정할 필요 없이 `.env`만 변경합니다:

```env
CHAOS_BACKEND=chaos_mesh
CHAOS_MESH_URL=http://chaos-mesh.chaos-testing:2333
```

내부적으로 `chaos_tools.py`의 팩토리 함수가 `ChaosMeshFaultInjector`를 자동 선택합니다.  
LLM이 호출하는 `inject_fault` / `recover_fault` @tool 시그니처는 변경되지 않습니다.

---

## 테스트 실행

```bash
pytest tests/ -v
```

```
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_pod_delete_success  PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_pod_delete_failure  PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_unknown_fault_type  PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_recover_success            PASSED
tests/test_chaos_tools.py::TestInjectFaultTool::test_inject_fault_calls_injector     PASSED
tests/test_chaos_tools.py::TestInjectFaultTool::test_inject_fault_returns_error_...  PASSED
tests/test_chaos_tools.py::TestDryRunFault::test_pod_exists_returns_ok               PASSED
tests/test_chaos_tools.py::TestDryRunFault::test_deployment_exists_returns_ok        PASSED
tests/test_chaos_tools.py::TestDryRunFault::test_target_not_found_returns_fail       PASSED
tests/test_chaos_tools.py::TestDryRunFault::test_subprocess_exception_returns_error  PASSED
tests/test_chaos_tools.py::TestInjectPodKill::test_success_returns_pod_kill_label    PASSED
tests/test_chaos_tools.py::TestInjectPodKill::test_failure_returns_error_string      PASSED
tests/test_chaos_tools.py::TestInjectNetworkDelay::test_success_returns_net_delay_.. PASSED
tests/test_chaos_tools.py::TestInjectNetworkDelay::test_default_delay_ms_is_500      PASSED
tests/test_chaos_tools.py::TestInjectNetworkDelay::test_failure_returns_error_string PASSED
tests/test_k8s_tools.py::TestGetPods::test_returns_pod_summary                       PASSED
tests/test_k8s_tools.py::TestGetPods::test_returns_error_on_failure                  PASSED
tests/test_k8s_tools.py::TestGetPods::test_empty_namespace_returns_no_pods_message   PASSED
tests/test_k8s_tools.py::TestGetDeploymentStatus::test_returns_replica_counts        PASSED
tests/test_k8s_tools.py::TestDescribePod::test_returns_events_section                PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_error_rate_exceeded      PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_error_rate_ok            PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_error_rate_zero_total_.. PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_cpu_usage_exceeded       PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_memory_usage_ok          PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_unsupported_metric_type  PASSED
tests/test_metrics_tools.py::TestCheckMetricThreshold::test_query_exception_returns  PASSED
tests/test_state.py::TestExperimentState::test_initial_status_is_pending             PASSED
tests/test_state.py::TestExperimentState::test_transition_updates_status             PASSED
tests/test_state.py::TestExperimentState::test_transition_appends_event_with_label   PASSED
tests/test_state.py::TestExperimentState::test_abort_sets_aborted_status             PASSED
tests/test_state.py::TestExperimentState::test_abort_logs_abort_prefix               PASSED
tests/test_state.py::TestExperimentState::test_timeline_returns_all_events_in_order  PASSED
tests/test_state.py::TestExperimentState::test_timeline_empty_returns_sentinel       PASSED
tests/test_state.py::TestExperimentState::test_reset_clears_all_fields               PASSED
tests/test_state.py::TestExperimentState::test_multiple_transitions_accumulate_events PASSED

36 passed in 4.25s
```

---

## AWS 실험 환경 구성

### 1. Amazon Bedrock (필수)

AWS 콘솔 → Bedrock → **Model access** 에서 `Claude Sonnet` 활성화 (us-east-1)  
IAM 사용자/역할에 아래 권한을 추가합니다:

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6"
}
```

### 2. Kubernetes 클러스터 (필수)

**옵션 A — EC2 단일 인스턴스 + minikube (권장 테스트 환경):**

IAM Role이 부여된 EC2 인스턴스(t3.medium 이상) 하나로 충분합니다.

```bash
# minikube 설치 (EC2 Amazon Linux 2023 기준)
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Docker 드라이버로 시작
minikube start --driver=docker

# kubeconfig 자동 설정 확인
kubectl get nodes
```

> `.env`의 `KUBECONFIG`는 비워두면 minikube가 설정한 `~/.kube/config`를 자동으로 사용합니다.

**옵션 B — EKS 클러스터 (프로덕션 유사 환경):**

```bash
eksctl create cluster --name chaos-lab --region us-east-1 --nodes 2 --node-type t3.medium
aws eks update-kubeconfig --name chaos-lab --region us-east-1
```

> 실험 후 `eksctl delete cluster --name chaos-lab` 으로 즉시 삭제해 비용을 절감하세요.

### 3. Prometheus (선택 — 없으면 Observability Agent 비활성)

**옵션 A — 클러스터 내부 설치 (권장):**

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus -n monitoring --create-namespace
kubectl port-forward svc/prometheus-server 9090:80 -n monitoring
```

`.env`에 `PROMETHEUS_URL=http://localhost:9090` 설정 후 사용.

**옵션 B — Amazon Managed Service for Prometheus (AMP):**  
관리형이라 운영 부담 없음. 별도 쿼리 엔드포인트 설정 필요.

### 최소 구성 비용 (월 기준)

**EC2 + minikube (테스트 추천):**

| 서비스 | 용도 | 예상 비용 |
|---|---|---|
| Amazon Bedrock | LLM 호출 | 사용량 기반 (실험 수준 ~$1 미만) |
| EC2 t3.medium × 1 | minikube 호스트 | ~$30 |
| Prometheus (in-cluster) | 메트릭 수집 | 무료 |

**EKS (프로덕션 유사 환경):**

| 서비스 | 용도 | 예상 비용 |
|---|---|---|
| Amazon Bedrock | LLM 호출 | 사용량 기반 (실험 수준 ~$1 미만) |
| EKS 클러스터 | 카오스 실험 대상 | ~$73 |
| t3.medium × 2 | 워커 노드 | ~$60 |
| Prometheus (in-cluster) | 메트릭 수집 | 무료 |

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Agent Framework | [Strands Agents SDK](https://github.com/strands-agents/sdk-python) |
| LLM | Claude Sonnet (Amazon Bedrock) |
| AWS SDK | boto3 |
| 상태 관리 | `ExperimentState` (dataclass + Enum) |
| Chaos (현재) | kubectl subprocess |
| Chaos (예정) | Chaos Mesh REST API |
| Observability | Prometheus HTTP API |
| K8s 클라이언트 | kubectl CLI |
| 테스트 | pytest + unittest.mock |

---

## 로드맵

- [x] Phase 1 — Admin + Chaos Agent (kubectl)
- [x] Phase 2 — Observability + Infra Agent 통합
- [x] Phase 3 — 상태 기반 동적 워크플로우, Planning Agent, Tool 세분화, 임계치 롤백
- [ ] Phase 4 — Chaos Mesh 백엔드 구현
- [ ] Phase 5 — Slack 알림 통합, 스케줄 자동화

---

## 라이선스

MIT
