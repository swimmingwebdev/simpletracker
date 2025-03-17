import connexion
from connexion import NoContent
import yaml
import logging.config
import json
import time
from pykafka import KafkaClient
from threading import Thread
from pykafka.common import OffsetType
import os

# Configurations
with open('/app/config/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Make sure the logs directory exists
log_directory = "/app/logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Logging
with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('analyzerLogger')

# Load Kafka config
KAFKA_HOSTNAME = app_config["events"]["hostname"] 
KAFKA_PORT = app_config["events"]["port"] 
KAFKA_TOPIC = app_config["events"]["topic"] 


def get_trackGPS_reading(index):
    client = KafkaClient(hosts=f"{KAFKA_HOSTNAME}:{KAFKA_PORT}")
    topic = client.topics[KAFKA_TOPIC.encode()]
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)

    counter = 0 
    logger.info("Kafka Consumer started, waiting for TrackGPS messages")

    for msg in consumer:
        try:
            message = msg.value.decode("utf-8")
            data = json.loads(message)

            if data["type"] == "TrackGPS":
                if counter == index:  
                    logger.info(f"Found TrackGPS at index {index}: {data['payload']}")
                    return data["payload"], 200
                counter += 1 

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON message.")

    logger.warning(f"No TrackGPS message at index {index}")
    return {"message": f"No TrackGPS message at index {index}"}, 404


def get_trackAlerts_reading(index):
    client = KafkaClient(hosts=f"{KAFKA_HOSTNAME}:{KAFKA_PORT}")
    topic = client.topics[KAFKA_TOPIC.encode()]
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)

    counter = 0
    logger.info("Kafka Consumer started, waiting for TrackAlerts messages")

    for msg in consumer:
        try:
            message = msg.value.decode("utf-8")
            data = json.loads(message)

            if data["type"] == "TrackAlerts":
                if counter == index:  
                    logger.info(f"Found TrackAlerts at index {index}: {data['payload']}")
                    return data["payload"], 200
                counter += 1 

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON message.")

    logger.warning(f"No TrackAlerts message at index {index}")
    return {"message": f"No TrackAlerts message at index {index}"}, 404

def get_event_stats():
    client = KafkaClient(hosts=f"{KAFKA_HOSTNAME}:{KAFKA_PORT}")
    topic = client.topics[KAFKA_TOPIC.encode()]
    consumer = topic.get_simple_consumer(reset_offset_on_start=True, consumer_timeout_ms=1000)

    num_gps_events = 0
    num_alert_events = 0
    logger.info("Kafka Consumer started, counting TrackGPS and TrackAlerts messages")

    for msg in consumer:
        try:
            message = msg.value.decode("utf-8")
            data = json.loads(message)

            if data["type"] == "TrackGPS":
                num_gps_events += 1
            elif data["type"] == "TrackAlerts":
                num_alert_events += 1

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON message.")

    logger.info(f"Stats retrieved - GPS Events: {num_gps_events}, Alert Events: {num_alert_events}")
    return {"num_gps_events": num_gps_events, "num_alert_events": num_alert_events}, 200

def process_messages():
    while True:  # Keep the consumer running even if it crashes
        try:
            hostname = f"{KAFKA_HOSTNAME}:{KAFKA_PORT}"
            client = KafkaClient(hosts=hostname)
            topic = client.topics[KAFKA_TOPIC.encode("utf-8")]

            consumer = topic.get_simple_consumer(
                consumer_group=b"event_group",
                reset_offset_on_start=False,
                auto_offset_reset=OffsetType.LATEST
            )

            logger.info("Kafka Consumer started, waiting for messages")
            
            for msg in consumer:
                try:
                    msg_str = msg.value.decode("utf-8")
                    msg = json.loads(msg_str)
                    logger.info("Message: %s" % msg)

                except json.JSONDecodeError:
                    logger.error("JSON Decoding Error")

                consumer.commit_offsets()

        except Exception as e:
            logger.error(f"Kafka Consumer Error: {e}")
            time.sleep(5) 
        
# to consume messages
def setup_kafka_thread():
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()

app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api("openapi.yml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    logger.info("Starting Analyzer Service")
    setup_kafka_thread()
    app.run(port=8110, host="0.0.0.0")