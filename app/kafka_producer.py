import json
import ssl
from aiokafka import AIOKafkaProducer
from .core.config import settings

producer: AIOKafkaProducer | None = None
ssl_context = ssl.create_default_context()

async def init_kafka():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers,
                                security_protocol="SASL_SSL",
                                sasl_mechanism="PLAIN",
                                sasl_plain_username=settings.kafka_username,
                                sasl_plain_password=settings.kafka_password,
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

    await producer.send_and_wait(settings.kafka_topic, data)