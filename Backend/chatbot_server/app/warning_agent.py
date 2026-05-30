import json 
from _utils.common import client, chatgpt_respone_format

USER_MONITOR_TEMPLATE = """
<대화록>을 읽고 아래의 json 형식에 따라 답하세요.
```
{{"{user}의 마지막 대화가 불쾌한 말을 하고 있는지":<true/false>, "{user}의 마지막 대화가 모순적인 말을 하고 있는지":<true/false>}}
```
<대화록>
"""
WARNINGS = ["{user}가 불쾌한 말을 하면 안된다고 지적할 것. '{user}야'라고 말을 시작해야 하며 20 단어를 넘기지 말 것", 
            "{user}가 모순된 말을 한다고 지적할 것. '무슨 소리하는 거니'라고 말을 시작해야 하며 20 단어를 넘기지 말 것"]

MIN_CONTEXT_SIZE = -3

class WarningAgent:

    def __init__(self, **kwargs):
        self.model = kwargs["model"]
        self.session_id = kwargs["session_id"]
        self.uid = kwargs["db_user_id"]
        self.name = kwargs["name"]
        self.assistant = kwargs["assistant"]
        # OpenAI role → 대화에 표시할 이름 (kwargs 키와 role 문자열은 다름)
        self._role_labels = {
            "user": self.name,
            "assistant": self.assistant,
        }
        self.user_monitor_template = (
            USER_MONITOR_TEMPLATE.format(user=self.name)
        )
        self.warnings = (
            [value.format(user=self.name) for value in WARNINGS]
        )

    def make_dialogue(self, context):
        dialogue_list = []
        for message in context:
            role = message["role"]
            speaker = self._role_labels.get(role)
            if speaker is None:
                continue
            dialogue_list.append(speaker + ": " + message["content"].strip())

        dialogue_str = "\n".join(dialogue_list)
        # print(f"dialogue_str:\n{dialogue_str}")
        return dialogue_str

    def monitor_user(self, context):        
        self.checked_list = []
        self.checked_context = []
        if len(context) <= abs(MIN_CONTEXT_SIZE): #최소 컨텍스트 크기(-3)
            return False
        self.checked_context = context[-3:]
        
        dialogue = self.make_dialogue(self.checked_context)        
        context = [
            {"role": "system", "content": f"당신은 유능한 의사소통 전문가입니다."},
            {"role": "user", "content": self.user_monitor_template + dialogue}
        ]
        try:
            response = json.loads(self.send_query(context))
            self.checked_list = [value for value in response.values()]
        except Exception as e:
            print(f"monitor-user except:[{e}]")
            return False
        
        print("self.checked_list(불쾌한 말, 모순적인 말):", self.checked_list)
        return sum(self.checked_list) > 0  # 파이썬에서 True는 숫자 1로 연산됨
          
    def warn_user(self):
        idx = [idx for idx, tf in enumerate(self.checked_list) if tf][0] 
        context = [
            {"role": "system", "content": f"당신은 {self.name}의 잘못된 언행에 대해 따끔하게 쓴소리하는 친구입니다. {self.warnings[idx]}"},
       ] + self.checked_context
        response = self.send_query(context, temperature=0.2, format_type="text")
        return response

    def send_query(self, context, temperature=0, format_type="json_object"):
        """
        OpenAI API에 쿼리를 보내고 응답 내용을 반환하는 메소드.

        Args:
            context (list): 챗봇 요청에 사용할 메시지 리스트(시스템, 유저 등).
            temperature (float, optional): 생성 다양성 제어 온도 파라미터. 기본값 0.
            format_type (str, optional): 반환되는 응답 포맷 지정("json_object" 또는 "text"). 기본값 "json_object".

        Returns:
            str: OpenAI 응답의 message.content. 
                 에러가 발생하면 경고 메시지 텍스트를 반환.
        """
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=context,
                temperature=temperature,
                response_format={ "type": format_type }
            ).model_dump()
            content = response['choices'][0]['message']['content']
            # print(f"query response:[{content}]")
            return content
        except Exception as e:
            print(f"Exception 오류({type(e)}) 발생:{e}")
            return chatgpt_respone_format("[경고 처리 중 문제가 발생했습니다. 잠시 뒤 이용해주세요.]")


