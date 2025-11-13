from datetime import datetime
from elasticsearch import AsyncElasticsearch
from decouple import config
import asyncio

es_client: AsyncElasticsearch | None = None


async def init_elk():
    global es_client

    if es_client is not None:
        return

    retry_interval = 5
    max_retries = 5

    for attempt in range(1, max_retries + 1):
        try:
            es_client = AsyncElasticsearch(hosts=[config("ELASTIC_URL")],
                                           basic_auth=(config("ELASTIC_USER"), config("ELASTIC_PASS")))

            if await es_client.ping():
                print("Elasticsearch client initialized successfully")
                return

            else:
                raise Exception("Ping failed")

        except Exception as e:
            print(f"Attempt {attempt}/{max_retries} - Failed to connect to Elasticsearch: {str(e)}")
            es_client = None

            if attempt < max_retries:
                await asyncio.sleep(retry_interval)

    print("All attempts to connect to Elasticsearch failed.")


async def shutdown_elk():
    global es_client

    if es_client:
        await es_client.close()
        es_client = None
        print("Elasticsearch client closed")


async def send_transaction(data: dict, local_kw=None):
    global es_client

    try:
        if es_client is None:
            print("Elasticsearch client not initialized - reinitializing...")
            await init_elk()

        if es_client is None:
            print("Still no Elasticsearch client available - skipping send")
            return

        clean_payload = {
            k: (v if v not in ["", None] else None)
            for k, v in data.items()
        }

        doc = {
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_id": data.get("transaction_id"),
            "payload": clean_payload,
        }

        res = await es_client.index(index=config("ELASTIC_INDEX"),
                                    document=doc)
        print(f"Sent transaction to ELK index '{config('ELASTIC_INDEX')}' with id={res['_id']}")

    except Exception as e:
        print(f"ERROR sending to Elasticsearch: {str(e)}")
        es_client = None
