# 버전을 명시하지 않은 범용 패키지 이름(python3-venv)으로 수정
sudo apt update && sudo apt install -y docker.io curl git python3-venv python3-pip

# 현재 ubuntu 유저가 sudo 없이 docker를 쓸 수 있게 권한 부여
sudo usermod -aG docker $USER
newgrp docker

# 미니쿠베 다운로드 및 설치
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# 미니쿠베 클러스터 시작 (2~3분 소요)
minikube start --driver=docker
>> minikube kubectl -- get pods -A
NAMESPACE     NAME                               READY   STATUS    RESTARTS   AGE
kube-system   coredns-7d764666f9-x5rng           0/1     Running   0          17s
kube-system   etcd-minikube                      1/1     Running   0          22s
kube-system   kube-apiserver-minikube            1/1     Running   0          22s
kube-system   kube-controller-manager-minikube   1/1     Running   0          22s
kube-system   kube-proxy-4nx5w                   1/1     Running   0          17s
kube-system   kube-scheduler-minikube            1/1     Running   0          23s
kube-system   storage-provisioner                1/1     Running   0          20s


# 1. 최신 버전의 kubectl 다운로드
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# 2. 실행 권한을 주고 /usr/local/bin 에 설치
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
>> kubectl get nodes
NAME       STATUS   ROLES           AGE    VERSION
minikube   Ready    control-plane   116s   v1.35.1

# 1. 먼저 uv 설치하기 (EC2에 아직 없다면)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# 프로젝트 파일 가져오기
git clone https://github.com/chikachik4/agent-app.git
cd agent-app

# 1. 가상환경 생성
uv venv

# 2. 가상환경 활성화
source .venv/bin/activate

# 3. 초고속 패키지 설치
uv pip install -r requirements.txt