import connexion
from connexion import NoContent
from models import Base, TrackAlerts, TrackLocations
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
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

logger = logging.getLogger('storageLogger')

# mysql
# Load database config
db_user = app_config["datastore"]["user"]
db_password = app_config["datastore"]["password"]
db_hostname = app_config["datastore"]["hostname"]
db_port = app_config["datastore"]["port"]
db_name = app_config["datastore"]["db"]
# Load Kafka config
KAFKA_HOSTNAME = app_config["events"]["hostname"] 
KAFKA_PORT = app_config["events"]["port"] 
KAFKA_TOPIC = app_config["events"]["topic"] 

# Initialize the engine
db_url = f"mysql+mysqldb://{db_user}:{db_password}@{db_hostname}:{db_port}/{db_name}"

# MySQL connection
MAX_RETRIES = 5
for i in range(MAX_RETRIES):
    try:
        engine = create_engine(db_url)
        # Create missing tables
        Base.metadata.create_all(engine)
        logger.info("Connected to MySQL")
        break
    except Exception as e:
        logger.error("MySQL not ready.")
        time.sleep(5)
else:
    logger.error("MySQL connection failed after retries.")
    exit(1)

def make_session():
    return sessionmaker(bind=engine)()

def parse_timestamp(timestamp):
    try:
        return datetime.strptime(timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")


# Get Location events
def get_trackGPS(start_timestamp, end_timestamp):
    session = make_session()
    try:
        start = parse_timestamp(start_timestamp)
        end = parse_timestamp(end_timestamp)

        statement = select(TrackLocations).where(
            TrackLocations.date_created >= start, 
            TrackLocations.date_created < end
            )
        results = [
            result.to_dict() 
            for result in session.execute(statement).scalars().all()
        ]

        logger.debug(f"Querying tracklocations from {start} to {end}")
        logger.info(f"Found {len(results)} trackGPS events (start: {start}, end: {end})")
        return results

    except Exception as e:
        logger.error(f"Error retrieving GPS data: {e}")
        return {"error": "Database error"}, 500
    
    finally:
        session.close()


# Get Alert events
def get_trackAlerts(start_timestamp, end_timestamp):
    session = make_session()

    try:
        start = parse_timestamp(start_timestamp)
        end = parse_timestamp(end_timestamp)
        
        statement = select(TrackAlerts).where(
            TrackAlerts.date_created >= start, 
            TrackAlerts.date_created < end
            )
        results = [
            result.to_dict() 
            for result in session.execute(statement).scalars().all()
        ]

        logger.debug(f"Querying trackalerts from {start} to {end}")
        logger.info(f"Found {len(results)} trackAlerts events (start: {start}, end: {end})")
        return results

    except Exception as e:
        logger.error(f"Error retrieving alerts data: {e}")
        return {"error": "Database error"}, 500
    
    finally:
        session.close()


def process_messages():
    """ Process event messages """
    while True:  # Keep the consumer running even if it crashes
        try:
            hostname = f"{KAFKA_HOSTNAME}:{KAFKA_PORT}"
            client = KafkaClient(hosts=hostname)

            if KAFKA_TOPIC.encode("utf-8") not in client.topics:
                logger.error(f"Kafka topic '{KAFKA_TOPIC}' does not exist. Retrying in 10s...")
                time.sleep(10)
                continue  # Skip iteration if topic does not exist

            topic = client.topics[KAFKA_TOPIC.encode("utf-8")]

            consumer = topic.get_simple_consumer(
                consumer_group=b"event_group",
                reset_offset_on_start=False,
                auto_offset_reset=OffsetType.LATEST
            )

            logger.info("Kafka Consumer started, waiting for messages")
            
            # Stay in the loop, waiting for new messages
            for msg in consumer:
                if msg is None:
                    continue  # No new messages, keep waiting

                try:
                    msg_str = msg.value.decode("utf-8")
                    msg = json.loads(msg_str)

                    logger.info("Message: %s" % msg)

                    payload = msg["payload"]

                    session = make_session()
                    timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
                    trace_id = payload["trace_id"]        

                    if msg["type"] == "TrackGPS":
                        event = TrackLocations(
                            device_id=payload["device_id"],
                            latitude=payload["latitude"],
                            longitude=payload["longitude"],
                            location_name=payload["location_name"],
                            timestamp=timestamp,
                            trace_id=trace_id
                        )
                        session.add(event)
                        session.commit()

                        # Logging when event is successfully stored
                        logger.debug(f"Stored trackGPS event with trace id {trace_id}")

                    elif msg["type"] == "TrackAlerts":
                        # Store the event2 to the DB 
                        event = TrackAlerts(
                            device_id=payload["device_id"],
                            latitude=payload["latitude"],
                            longitude=payload["longitude"],
                            location_name=payload["location_name"],
                            alert_desc=payload["alert_desc"],
                            timestamp=timestamp,
                            trace_id=trace_id 
                        )
                        session.add(event)
                        session.commit()
                        
                        # Use DEBUG level for stored events as specified
                        logger.debug(f"Stored event trackAlerts with a trace id of {trace_id}")
                    
                finally:
                    session.close()  # Ensure session closes every time
                
                consumer.commit_offsets()
        
        except Exception as e:
            logger.error(f"Kafka Consumer crashed: {e}")
            time.sleep(5) # Wait before restarting
        

# thread to consume messages
def setup_kafka_thread():
    t1 = Thread(target=process_messages)
    t1.setDaemon(True)
    t1.start()

app = connexion.FlaskApp(__name__, specification_dir='.')
app.add_api("openapi.yml", strict_validation=True, validate_responses=True)

if __name__ == "__main__":
    logger.info("Storage Service received")
    setup_kafka_thread()
    app.run(port=8090, host="0.0.0.0")