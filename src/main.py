import logging
import os

import boto3
from dotenv import load_dotenv
from strands.models.bedrock import BedrockModel

from src.agents.admin import AdminAgent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_bedrock_model() -> BedrockModel:
    session = boto3.Session(
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    return BedrockModel(
        boto_session=session,
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    )


def main() -> None:
    logger.info("Strands AIOps & Chaos Agent 초기화 중...")
    model = create_bedrock_model()
    admin = AdminAgent(model=model)
    logger.info("준비 완료. 종료하려면 'exit' 또는 'quit'을 입력하세요.")
    print("\n=== Strands AIOps & Chaos Multi-Agent System ===")
    print("예시: 'default 네임스페이스의 nginx-pod에 카오스 테스트 시작해'\n")

    while True:
        try:
            user_input = input("User> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("종료합니다.")
            break
        response = admin.run(user_input)
        print(f"\nAdmin> {response}\n")


if __name__ == "__main__":
    main()
