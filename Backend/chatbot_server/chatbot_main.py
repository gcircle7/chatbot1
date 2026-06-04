from app.chatbot_server import ChatbotServer
import atexit

# 챗봇 서버 인스턴스 생성
cb_server = ChatbotServer() 

@atexit.register
def shutdown():
    print("ChatbotServer shutting down...")
    cb_server.stop()

if __name__ == "__main__":
    cb_server.run()
