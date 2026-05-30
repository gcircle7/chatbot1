from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")

import os
from datetime import datetime, timedelta
import pytz 

def chatgpt_respone_format(message, finish_reason="stop", useCallback=False):
    """카카오 i 오픈빌더 스킬 서버 응답 포맷."""
    if useCallback:
        return {"version": "2.0", "useCallback": True}
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": message or ""}}],
        },
    }
                
def today():
    korea = pytz.timezone('Asia/Seoul')# 한국 시간대를 얻습니다.
    now = datetime.now(korea)# 현재 시각을 얻습니다.
    return(now.strftime("%Y%m%d"))# 시각을 원하는 형식의 문자열로 변환합니다.

def yesterday():    
    korea = pytz.timezone('Asia/Seoul')# 한국 시간대를 얻습니다.
    now = datetime.now(korea)# 현재 시각을 얻습니다.
    one_day = timedelta(days=1)    # 하루 (1일)를 나타내는 timedelta 객체를 생성합니다.
    yesterday = now - one_day # 현재 날짜에서 하루를 빼서 어제의 날짜를 구합니다.
    return yesterday.strftime('%Y%m%d') # 어제의 날짜를 yyyymmdd 형식으로 변환합니다.

def currTime():
    # 한국 시간대를 얻습니다.
    korea = pytz.timezone('Asia/Seoul')
    # 현재 시각을 얻습니다.
    now = datetime.now(korea)
    # 시각을 원하는 형식의 문자열로 변환합니다.
    formatted_now = now.strftime("%Y.%m.%d %H:%M:%S")
    return(formatted_now)
