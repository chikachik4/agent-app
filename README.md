# Strands AIOps & Chaos Multi-Agent System

Kubernetes 환경의 인프라 모니터링과 카오스 엔지니어링을 자동화하는 **멀티 에이전트 시스템**입니다.  
[Strands Agents SDK](https://github.com/strands-agents/sdk-python) 기반으로 구축되었으며, **Amazon Bedrock**을 통해 Claude 3.5 Sonnet 모델을 호출합니다.

---

## 주요 기능

- **자연어 명령 한 줄**로 카오스 실험 전 과정 자동 실행
- Pod 삭제·네트워크 지연 등 장애 주입 → Prometheus 메트릭 관측 → K8s 복구 검증 → 결과 리포트까지 **완전 자동화**
- `CHAOS_BACKEND` 환경변수 하나로 **kubectl ↔ Chaos Mesh 백엔드 교체** 가능 (코드 수정 불필요)

---

## 아키텍처

```
User (자연어 명령)
        │
        ▼
┌─────────────────────┐
│    Admin Agent      │  ← 오케스트레이터
│  (Claude 3.5 Sonnet │
│   via Bedrock)      │
└──────┬──────┬───────┘
       │      │      │
       ▼      ▼      ▼
 Chaos    Observa-  Infra
 Agent    bility    Agent
   │      Agent      │
   │        │        │
kubectl  Prometheus  kubectl
delete   /api/v1/   get pods
pod      query      describe
```

### 에이전트 역할

| 에이전트 | 역할 | 주요 도구 |
|---|---|---|
| **Admin** | 오케스트레이션 & 결과 취합 | sub-agent 래퍼 3개 |
| **Chaos** | 장애 주입 | `inject_fault`, `recover_fault` |
| **Observability** | 메트릭 관측 | `query_prometheus`, `get_error_rate` |
| **Infra** | 복구 상태 검증 | `get_pods`, `get_deployment_status` |

---

## 디렉토리 구조

```
agent/
├── .env                        # AWS 자격증명 및 환경변수 (git 제외)
├── requirements.txt
├── src/
│   ├── main.py                 # 진입점 — Bedrock 초기화 & 대화 루프
│   ├── agents/
│   │   ├── base.py             # BaseAgent 추상 클래스
│   │   ├── admin.py            # 오케스트레이터
│   │   ├── chaos.py
│   │   ├── observability.py
│   │   └── infra.py
│   └── tools/
│       ├── chaos_tools.py      # 장애 주입 추상화 레이어 (kubectl / Chaos Mesh)
│       ├── k8s_tools.py        # K8s 상태 조회
│       └── metrics_tools.py    # Prometheus 쿼리
└── tests/
    ├── test_chaos_tools.py
    └── test_k8s_tools.py
```

---

## 시작하기

### 사전 요구사항

- Python 3.10+
- `kubectl` 설치 및 클러스터 접근 가능
- AWS 계정 및 Bedrock `claude-3-5-sonnet` 모델 접근 권한
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

`.env` 파일을 열어 실제 값을 채웁니다:

```env
# AWS Credentials & Region (Bedrock)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Kubernetes
KUBECONFIG=/path/to/kubeconfig

# Prometheus
PROMETHEUS_URL=http://prometheus.monitoring:9090

# Chaos Backend: "kubectl" (기본값) 또는 "chaos_mesh"
CHAOS_BACKEND=kubectl
```

### 실행

```bash
python src/main.py
```

```
=== Strands AIOps & Chaos Multi-Agent System ===
예시: 'default 네임스페이스의 nginx-pod에 카오스 테스트 시작해'

User> default 네임스페이스의 nginx-deployment에 카오스 테스트 시작해

Admin> [실험 타임라인]
  1. 장애 주입: nginx-pod-xxx 삭제 완료
  2. 메트릭 관측: 5xx 에러율 12.4% 스파이크 감지 (30초간)
  3. 복구 확인: 새 Pod Running, desired=3 / ready=3
  결론: Auto-healing 정상 동작 확인 ✓
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
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_pod_delete_success PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_pod_delete_failure PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_inject_unknown_fault_type  PASSED
tests/test_chaos_tools.py::TestKubectlFaultInjector::test_recover_success            PASSED
tests/test_chaos_tools.py::TestInjectFaultTool::test_inject_fault_calls_injector     PASSED
tests/test_chaos_tools.py::TestInjectFaultTool::test_inject_fault_returns_error_...  PASSED
tests/test_k8s_tools.py::TestGetPods::test_returns_pod_summary                       PASSED
tests/test_k8s_tools.py::TestGetPods::test_returns_error_on_failure                  PASSED
tests/test_k8s_tools.py::TestGetPods::test_empty_namespace_returns_no_pods_message   PASSED
tests/test_k8s_tools.py::TestGetDeploymentStatus::test_returns_replica_counts        PASSED
tests/test_k8s_tools.py::TestDescribePod::test_returns_events_section                PASSED

11 passed in 0.89s
```

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| Agent Framework | [Strands Agents SDK](https://github.com/strands-agents/sdk-python) |
| LLM | Claude 3.5 Sonnet (Amazon Bedrock) |
| AWS SDK | boto3 |
| Chaos (현재) | kubectl subprocess |
| Chaos (예정) | Chaos Mesh REST API |
| Observability | Prometheus HTTP API |
| K8s 클라이언트 | kubectl CLI |
| 테스트 | pytest + unittest.mock |

---

## 로드맵

- [x] Phase 1 — Admin + Chaos Agent (kubectl)
- [x] Phase 2 — Observability + Infra Agent 통합
- [ ] Phase 3 — Chaos Mesh 백엔드 구현, Cost Agent 추가
- [ ] Phase 4 — Slack 알림 통합, 스케줄 자동화

---

## 라이선스

MIT