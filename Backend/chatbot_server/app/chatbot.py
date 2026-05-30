from _utils.common import client, chatgpt_respone_format
import math
from app.memory_manager import MemoryManager
from app.chat_history_manager import ChatHistoryManager
import threading
import time
from app.warning_agent import WarningAgent

class Chatbot:
    
    def __init__(self, model, system_role, instruction, **kwargs):
        self.context = [{"role": "system", "content": system_role}]
        self.model = model
        self.instruction = instruction
        self.max_token_size = 16 * 1024
        self.available_token_rate = 0.9
        self.session_id = kwargs["session_id"]
        self.db_user_id = kwargs["db_user_id"]
        self.name = kwargs["user_name"]
        self.assistant = kwargs["assistant"]
        self.memoryManager = MemoryManager(session_id=self.session_id, db_user_id=self.db_user_id, name=self.name, assistant=self.assistant)
        # self.context.extend(self.memoryManager.restore_chat())
        self.chatHistoryManager = ChatHistoryManager(session_id=self.session_id, db_user_id=self.db_user_id)
        self.context.extend(self.chatHistoryManager.restore_session_chats())
        self.warningAgent = self._create_warning_agent()

        # print(f"context count: {len(self.context)}")        
        # for message in self.context:
        #     print(f"{message['role']} : {message['content']}")
        

    def _create_warning_agent(self):
        return WarningAgent(
                    model=self.model,
                    session_id=self.session_id,
                    db_user_id=self.db_user_id,
                    name=self.name,
                    assistant=self.assistant,
               )

    def add_user_message(self, user_message):
        self.context.append({"role": "user", "content": user_message, "saved" : False})
        print(f"user_message: {user_message}")

    def add_ai_message(self, response):
        resp_message = {
            "role" : response['choices'][0]['message']["role"],
            "content" : response['choices'][0]['message']["content"],
            "saved" : False
        }
        self.context.append(resp_message)
        print("ai_message: ", resp_message["content"]) 

    def get_response_content(self):
        return self.context[-1]['content']

    def _send_request(self):
        try:
            response = client.chat.completions.create(
                model=self.model, 
                messages=self.to_openai_context(),
                temperature=0.5,
                top_p=1,
                max_tokens=256,
                frequency_penalty=0,
                presence_penalty=0
            ).model_dump()
        except Exception as e:
            print(f"Exception 오류({type(e)}) 발생:{e}")
            if 'maximum context length' in str(e):
                if len(self.context) > 2:
                    self.context = [self.context[0]] + self.context[2:]
                    return self._send_request()
                else:
                    # 마지막 답변을 요약하여 줄여서 전달 필요 (차후 구현)
                    print("context size is too small", len(self.context))
                    return False, chatgpt_respone_format("[내 찐친 챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]", finish_reason="ERROR")
            else: 
                return False, chatgpt_respone_format("[내 찐친 챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]", finish_reason="ERROR")
        return True, response
  
    def send_request(self):
        if self.warningAgent.monitor_user(self.context):
            return True, chatgpt_respone_format(self.warningAgent.warn_user(), "warning") 
        else:    
            memory_instruction = self.retrieve_memory()
            self.context[-1]['content'] += self.instruction + (memory_instruction if memory_instruction else "") 
            # if memory_instruction:
            #   print("memory check end: ", self.context[-1]['content'])
            tf, response = self._send_request()   
            return tf, response
    
    def retrieve_memory(self):
        user_message = self.context[-1]['content']
        # print("memory check start: ", user_message)
        if not self.memoryManager.needs_memory(user_message):
            return

        memory = self.memoryManager.retrieve_memory(user_message)  
        if memory is not None:
            whisper = (f"[귓속말]\n{self.assistant}야! 기억 속 대화 내용이야. 앞으로 이 내용을 참조하면서 답해줘. "
                       f"알마 전에 나누었던 대화라는 점을 자연스럽게 말해줘:\n{memory}")
            # self.add_user_message(whisper)
            return whisper
        else:
            return "[기억이 안난다고 답할 것!]"   

    def clean_context(self):
        for idx in reversed(range(len(self.context))):
            if self.context[idx]["role"] == "user":
                self.context[idx]["content"] = self.context[idx]["content"].split("instruction:\n")[0].strip()
                break
    
    def handle_token_limit(self, response):
        # 누적 토큰 수가 임계점을 넘지 않도록 제어한다.
        try:
            current_usage_rate = response['usage']['total_tokens'] / self.max_token_size
            exceeded_token_rate = current_usage_rate - self.available_token_rate
            if exceeded_token_rate > 0:
                remove_size = math.ceil(len(self.context) / 10)
                self.context = [self.context[0]] + self.context[remove_size+1:]
        except Exception as e:
            print(f"handle_token_limit exception:{e}")
    
    def to_openai_context(self):
        return [{"role":v["role"], "content":v["content"]} for v in self.context]
    
    def save_one_chat(self):
        return self.chatHistoryManager.save_one_chat(self.context[-1])    
    
    def save_chat(self):
        self.memoryManager.save_chat(self.context)    
