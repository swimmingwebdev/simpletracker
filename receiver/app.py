import connexion
from connexion import NoContent
from datetime import datetime
import yaml 
import logging.config
import time
from pykafka import KafkaClient
import json
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

logger = logging.getLogger('receiverLogger')

# URL from config
EVENT1_URL = app_config["eventstore1"]["url"]
EVENT2_URL = app_config["eventstore2"]["url"] 
# Load Kafka config
KAFKA_HOSTNAME = app_config["events"]["hostname"] 
KAFKA_PORT = app_config["events"]["port"] 
KAFKA_TOPIC = app_config["events"]["topic"] 

# Kafka Connection (Persistent)
try:
    client = KafkaClient(hosts=f"{KAFKA_HOSTNAME}:{KAFKA_PORT}")
    topic = client.topics[KAFKA_TOPIC.encode("utf-8")]
    producer = topic.get_sync_producer()
    logger.info(f"Connected to Kafka at {KAFKA_HOSTNAME}:{KAFKA_PORT}")
except Exception as e:
    logger.error(f"Failed to connect to Kafka: {str(e)}")
    producer = None

# Event 1
def trackGPS(body):

    trace_id = time.time_ns()

    # Logging when an event is received
    logger.info(f"Received event trackGPS of [Trace ID: {trace_id}].")

    # 2025-02-11T15:30:00Z >>> 2025-02-11 15:30:00+00:00
    received_timestamp = datetime.fromisoformat(body.get("timestamp", "").replace("Z", "+00:00"))

    data = {
            "device_id": body["device_id"],
            "latitude": body["latitude"],
            "longitude": body["longitude"],
            "location_name": body.get("location_name", "unknown"),
            "timestamp": received_timestamp.isoformat().replace("+00:00", "Z"),
            "trace_id" : trace_id,
    }

    msg = { 
        "type": "TrackGPS",
        "datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": data
    }

    msg_str = json.dumps(msg)

    # Send data to kafka
    if producer:
        try:
            producer.produce(msg_str.encode('utf-8'))
            logger.info(f"[Trace ID: {trace_id}] Successfully sent to Kafka topic '{KAFKA_TOPIC}'.")
        except Exception as e:
            logger.error(f"[Trace ID: {trace_id}] Kafka error: {str(e)}")
            return {"error": "Kafka failure"}, 500
    else:
        logger.error(f"[Trace ID: {trace_id}] Kafka producer is not available.")
        return {"error": "Kafka is down"}, 500

    return NoContent, 201


# Event 2
def trackAlerts(body):
    trace_id = time.time_ns()

    # Logging when an event is received
    logger.info(f"Received event trackAlerts with a trace id of [Trace ID: {trace_id}].")

    received_timestamp = datetime.fromisoformat(body.get("timestamp", "").replace("Z", "+00:00"))

    data = {
            "device_id": body["device_id"],
            "latitude": body["latitude"],
            "longitude": body["longitude"],
            "location_name": body.get("location_name", "unknown"),
            "alert_desc": body.get("alert_desc", "No description provided."),
            "timestamp": received_timestamp.isoformat().replace("+00:00", "Z"),
            "trace_id" : trace_id,
    }

    msg = { 
        "type": "TrackAlerts",
        "datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "payload": data
    }
    msg_str = json.dumps(msg)

    # Send to Kafka
    if producer:
        try:
            producer.produce(msg_str.encode('utf-8'))
            logger.info(f"[Trace ID: {trace_id}] Successfully sent to Kafka topic '{KAFKA_TOPIC}'.")
        except Exception as e:
            logger.error(f"[Trace ID: {trace_id}] Kafka error: {str(e)}")
            return {"error": "Kafka failure"}, 500
    else:
        logger.error(f"[Trace ID: {trace_id}] Kafka producer is not available.")
        return {"error": "Kafka is down"}, 500

    return NoContent, 201

app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api("openapi.yml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    logger.info("Receiver Service started")
    app.run(port=8080, host="0.0.0.0")