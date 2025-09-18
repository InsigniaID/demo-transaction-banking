import paho.mqtt.client as paho
from decouple import config
from paho import mqtt


# Callback kalau berhasil connect
def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNACK received with code %s." % rc)

# Callback publish sukses
def on_publish(client, userdata, mid, properties=None):
    print("Message published, mid: " + str(mid))

# Callback subscribe sukses
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))

def on_message(client, userdata, msg):
    print(f"[RECEIVED] {msg.topic} | QoS {msg.qos} | {msg.payload.decode()}")


client = paho.Client(client_id="", userdata=None, protocol=paho.MQTTv5)
client.on_connect = on_connect
client.on_publish = on_publish
client.on_subscribe = on_subscribe
client.on_message = on_message

client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
client.username_pw_set(config("UNAME"), config("PASS"))
client.connect(config("BROKER"), config("PORT", cast=int))
client.loop_start()
client.subscribe(config("TOPIC"), qos=1)


def publish(topic: str, payload: str, qos: int = 1, retain: bool = False):
    return client.publish(topic, payload, qos=qos, retain=retain)
