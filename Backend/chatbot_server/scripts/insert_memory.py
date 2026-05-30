from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")

from openai import OpenAI
import os
import pinecone
from pymongo import MongoClient
import json

from pinecone import Pinecone

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("jjinchin-memory")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

mongo_cluster = MongoClient(os.getenv("MONGO_CLUSTER_URI"))
mongo_memory_collection = mongo_cluster["jjinchin"]["memory"]

embedding_model = "text-embedding-3-small"

with open("madefiles\\대화내용요약.json", "r", encoding="utf-8") as f:
    summaries_list = json.load(f)

mongo_memory_collection.delete_many({})

next_id = 1

for list_idx, summaries in enumerate(summaries_list):
    date = f"202605{list_idx+1:02}"

    for summary in summaries:
        vector = client.embeddings.create(
            input=summary["요약"],
            model=embedding_model
        ).data[0].embedding

        metadata = {"date": date, "keyword": summary["주제"]}
        pinecone_index.upsert(vectors=[(str(next_id), vector, metadata)])

        query = {"_id": next_id}
        newvalues = {"$set": {"date": date, "keyword": summary["주제"],  "summary" : summary["요약"]}} 
        mongo_memory_collection.update_one(query, newvalues, upsert=True)
        
        if (next_id) % 5 == 0:    
            print(f"id: {next_id}")
            
        next_id += 1
        
        