from confluent_kafka.admin import AdminClient, NewTopic
from decouple import config

conf = {
    "bootstrap.servers": config("KAFKA_BOOTSTRAP_SERVERS"),
    "sasl.mechanisms": "PLAIN",
    "security.protocol": "SASL_SSL",
    "sasl.username": config("KAFKA_USERNAME"),
    "sasl.password": config("KAFKA_PASSWORD"),
}

admin_client = AdminClient(conf)
new_topic = "anomaly_detection"
topic_list = [NewTopic(new_topic, num_partitions=1, replication_factor=3)]
fs = admin_client.create_topics(topic_list)

for topic, f in fs.items():
    try:
        f.result()
        print(f"Create topic '{topic}' successfully")

    except Exception as e:
        print(f"Fail create topic '{topic}', error\n: {e}")
