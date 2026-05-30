from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
import os

# load_dotenv(".env")
load_dotenv(".env")
print(f"실행 루트 폴더: {Path.cwd()}")
print(f"현재 파일의 폴더 위치: {Path(__file__).resolve().parent}")

_uri = (os.getenv("MONGO_CLUSTER_URI") or "").strip()
if not _uri:
    raise SystemExit(
        "MONGO_CLUSTER_URI가 비어 있습니다. chapter11/.env에 Atlas 연결 문자열을 설정하세요.\n"
        "예: MONGO_CLUSTER_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/"
    )

# cluster=MongoClient("mongodb+srv://<id>:<password>@cluster0.ov3wpli.mongodb.net/?retryWrites=true&w=majority")
cluster = MongoClient(_uri)
db=cluster["jjinchin"]
profiles = db["profiles"]
collection = db["chats"]

print("--------------------------------\n")
results = collection.find({'date': '20260521', 'uid': 'A1234567890'})
print(f"type: {type(results)}")
for rec in results:
    print(type(rec), rec)
    # for col in list(rec.keys()):
    #     if col != '_id':
    #         print(col, "=", rec[col], end=" ")
    # print("\n")
print("--------------------------------")

utterance = {
	"uid": "A1234567890",
	"date": "20260521",	
	"role":"assistant",
	"content":"민지야, 날씨 진짜 끝내준다! 🌞 산책 가자!"
}
collection.insert_one(utterance)

# exit()

profile = {
	"uid": "A1234567890",
	"date": "20260521",
    "name": "고비",
    "age": 26,
    "job": "대중음악 작곡가",
    "character": "당신은 진지한 것을 싫어하며, 항상 밝고 명랑한 성격임",
    "best friend": {
        "name": "김민지",
        "situations": [
            "회사 생활에 의욕을 찾지 못하고 창업을 준비하고 있음",
            "매운 음식을 좋아함",
            "가장 좋아하는 가수는 '아이유'",
        ],
    },
} 

if not profiles.find_one({"uid": profile["uid"], "date": profile["date"]}):
    profiles.insert_one(profile)

for result in profiles.find({}):
    print(result)
