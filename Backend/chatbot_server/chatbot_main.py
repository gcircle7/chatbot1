import logging

from _utils.logging_config import setup_logging

# 로깅을 가장 먼저 초기화(콘솔 UTF-8 + data/log 일자 파일)
setup_logging("chatbot_server")
logger = logging.getLogger(__name__)

from app.chatbot_server import ChatbotServer
import atexit

# 챗봇 서버 인스턴스 생성
cb_server = ChatbotServer()


@atexit.register
def shutdown():
    logger.info("ChatbotServer shutting down...")
    cb_server.stop()


if __name__ == "__main__":
    cb_server.run()
