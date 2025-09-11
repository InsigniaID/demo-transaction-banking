import json
import ssl
from aiokafka import AIOKafkaProducer
from .core.config import settings

producer: AIOKafkaProducer | None = None
ssl_context = ssl.create_default_context()

async def init_kafka():
    global producer
    try:
        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers,
                                    security_protocol="SASL_SSL",
                                    sasl_mechanism="PLAIN",
                                    sasl_plain_username=settings.kafka_username,
                                    sasl_plain_password=settings.kafka_password,
                                    ssl_context=ssl_context,
                                    value_serializer=lambda v: json.dumps(v).encode("utf-8"))
        await producer.start()
        print("✅ Kafka producer initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Kafka producer: {str(e)}")
        producer = None  # Ensure producer remains None if initialization fails

async def shutdown_kafka():
    global producer

    if producer:
        await producer.stop()
        producer = None

async def send_transaction(data: dict, local_kw=None):
    try:
        if not producer:
            print("WARNING: Kafka producer not initialized - skipping Kafka send")
            return
        
        await producer.send_and_wait(settings.kafka_topic, data)
        print(f"Successfully sent transaction to Kafka: {data.get('transaction_id', 'unknown')}")
    except Exception as e:
        print(f"ERROR: Failed to send to Kafka: {str(e)}")
        # Don't raise the exception - just log and continue
        # This prevents 500 errors when Kafka is unavailable