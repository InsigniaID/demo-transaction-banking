import json
import ssl
from aiokafka import AIOKafkaProducer
from decouple import config

producer: AIOKafkaProducer | None = None
ssl_context = ssl.create_default_context()

async def init_kafka():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=config("KAFKA_BOOTSTRAP_SERVERS"),
                                security_protocol="SASL_SSL",
                                sasl_mechanism="PLAIN",
                                sasl_plain_username=config("KAFKA_USERNAME"),
                                sasl_plain_password=config("KAFKA_PASSWORD"),
                                ssl_context=ssl_context,
                                value_serializer=lambda v: json.dumps(v).encode("utf-8"))
    await producer.start()

async def shutdown_kafka():
    global producer

    if producer:
        await producer.stop()
        producer = None

async def send_transaction(data: dict, local_kw=None):
    if not producer:
        raise RuntimeError("Kafka producer not initialized")

    await producer.send_and_wait(config("KAFKA_TOPIC"), data)