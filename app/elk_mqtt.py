from elasticsearch import Elasticsearch
from decouple import config
from datetime import datetime

es = Elasticsearch(hosts=[config("ELASTIC_URL", default="http://localhost:9200")],
                   basic_auth=(config("ELASTIC_USER", default="elastic"), config("ELASTIC_PASS", default="changeme")))

INDEX_NAME = config("ELASTIC_INDEX", default="app-logs")

def publish_to_elk(topic: str, payload: str):
    doc = {
        "topic": topic,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        res = es.index(index=INDEX_NAME, document=doc)
        print(f"[PUBLISHED to ELK] {res['result']} | topic={topic}")
        return res

    except Exception as e:
        print(f"[ERROR ELK] {e}")
        return None
