# CLAUDE.md — Strands AIOps & Chaos Agent 프로젝트 명세

> **Claude에게**: 이 디렉토리에서는 웹 서비스 로직은 무시하고, 오직 **Strands SDK 기반의 멀티 에이전트 시스템(Python) 개발**에만 집중하세요.

## 1. 프로젝트 개요
- **목적**: Kubernetes 환경의 인프라 모니터링과 카오스 엔지니어링을 자동화하는 Multi-Agent 시스템 구축
- **핵심 프레임워크**: `strands-agents`, `strands-agents-tools` (Python)
- **AI 모델 및 환경**: **Amazon Bedrock** 환경의 Claude 3.5 Sonnet (boto3 연동 필요)

## 2. 에이전트 설계 및 확장성 (추상화 패턴)
향후 외부 툴(예: Chaos Mesh) 도입을 위해 모든 액션은 **추상화된 Tool 인터페이스**로 구현합니다.

1. **Admin Agent (오케스트레이터)**
   - 사용자의 카오스 테스트 명령 분석 및 타 에이전트 지시
   - 결과 리포트 종합 (Slack 알림 확장 대비)

2. **Chaos Agent (장애 주입 담당)**
   - **(현재)** `kubectl` 기반의 가벼운 장애 주입 (예: `delete_pod_tool`)
   - **(미래 대비)** 추후 Chaos Mesh API를 호출하도록 툴 내부 로직만 교체할 수 있게 `inject_fault` 형태의 범용적인 Tool 인터페이스로 설계

3. **Observability Agent (관측 담당)**
   - Prometheus 메트릭 조회 (CPU/Memory, 5xx 에러 등)

4. **Infra Agent (복구/상태 확인 담당)**
   - K8s 클러스터 리소스 복구 여부 검증 (`kubectl get/describe` 활용)

## 3. 핵심 자동화 시나리오 (구현 목표)
1. **장애 주입**: Chaos Agent가 특정 Namespace의 타겟 Pod에 대해 장애 주입 툴 실행.
2. **영향 관측**: Observability Agent가 Prometheus를 조회하여 트래픽/메트릭 변화 감지.
3. **복구 확인**: Infra Agent가 K8s 상태를 조회하여 Auto-healing(새 Pod 생성 및 Running) 검증.
4. **결과 보고**: Admin Agent가 실험 결과 요약.

## 4. 디렉토리 구조 가이드
최상위 폴더에는 설정 파일만 두고, 소스 코드는 `src/`에 배치합니다.

```text
agent/
├── .venv/            (가상환경)
├── .env              (AWS 자격증명 등 환경변수)
├── CLAUDE.md         (Claude 지침서 - 루트에 위치)
└── src/
    ├── main.py       (Bedrock Client 설정 및 에이전트 초기화)
    ├── agents/       (에이전트 클래스 정의)
    │   ├── admin.py
    │   ├── chaos.py
    │   ├── observability.py
    │   └── infra.py
    └── tools/        (추상화된 @tool 함수들)
        ├── chaos_tools.py    (현재는 kubectl, 추후 ChaosMesh로 변경될 영역)
        ├── k8s_tools.py      (순수 상태 조회용)
        └── metrics_tools.py