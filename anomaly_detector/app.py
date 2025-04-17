import connexion
import os
import yaml
import json
import logging.config
from datetime import datetime, timezone
import httpx
from starlette.middleware.cors import CORSMiddleware
from connexion.middleware import MiddlewarePosition

# Load app config
with open("/app/config/app_conf.yml", "r") as f:
    app_config = yaml.safe_load(f.read())

# Setup logging
LOG_DIRECTORY = "/app/logs"
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)

with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('anomalyLogger')

ANOMALY_FILE = app_config["datastore"]
ANALYZER_URL = app_config["analyzer"]["url"]
STORAGE_URL = app_config["storage"]["url"]
PROCESSING_URL = app_config["processing"]["url"]

KAFKA_HOSTNAME = app_config["events"]["hostname"]
KAFKA_PORT = app_config["events"]["port"]
KAFKA_TOPIC = app_config["events"]["topic"]

logger.info(f"Kafka config - Host: {KAFKA_HOSTNAME}, Port: {KAFKA_PORT}, Topic: {KAFKA_TOPIC}")

# Load previous results
def load_results():
    if os.path.exists(ANOMALY_FILE):
        with open(ANOMALY_FILE, 'r') as f:
            return json.load(f)
    else:
        anomaly = {
            "id": 0,
            "event_id": 0,
            "trace_id": 0,
            "event_type": None,
            "anomaly_type": None,
            "description": None
        }
    with open(ANOMALY_FILE, "w") as f:
        json.dump(ANOMALY_FILE, f, indent=2)   
    return anomaly

# Save new anomaly_Detector result
def save_results(data):
    with open(ANOMALY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# to create a key for an event based on trace_id
def event_key(event):
    return str(event.get("trace_id"))

# Fetch analyzer queue data
async def fetch_all_analyzer_events(analyzer_url, event_type):
    results = []
    index = 0
    while True:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{analyzer_url}/track/{event_type}?index={index}")
                if response.status_code != 200:
                    break
                results.append(response.json())
                index += 1
            except Exception as e:
                logger.error(f"Error fetching {event_type} from analyzer at index {index}: {str(e)}")
                break
    return results

def clean_timestamp(ts):
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception as e:
        logger.error(f"Invalid timestamp format: {ts}. Resetting to default.")
        return "2000-01-01T00:00:00Z"

# PUT /update
# to fetch events from storage and analyzer and comparing them
async def update_anomalies():
    logger.debug("Accessing the update endpoint of anomaly_detector service")
    start_time = datetime.now()

    try:
        anomaly = load_results()

        gps_queue = await fetch_all_analyzer_events(ANALYZER_URL, "locations")
        alerts_queue = await fetch_all_analyzer_events(ANALYZER_URL, "alerts")

        if not isinstance(gps_queue, list): gps_queue = []
        if not isinstance(alerts_queue, list): alerts_queue = []

        all_queue = {event_key(e): e for e in gps_queue + alerts_queue}

        item = [v for k, v in all_queue.items() if k["latitude"] > 1000 or k["longitude"] > 1000]

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        result = {
            "processing_time_ms": processing_time,
            "id": item["id"],
            "event_id": item["event_id"],
            "trace_id": item["trace_id"],
            "event_type": item["event_type"],
            "anomaly_type": item["anomaly_type"],
            "description" : item["description"]
            
        }

        save_results(result)
        logger.debug(
            f"anomaly is detected and added to the JSON file | the value detected={processing_time} | threshold exceeded={processing_time}"
        )

        logger.info(
            f"anomaly_detector completed | processing_time_ms={processing_time}"
        )

        return {"processing_time_ms": processing_time}, 200

    except Exception as e:
        logger.error(f"Error during anomaly detecting: {str(e)}")
        return {"message": "Error during anomaly detecting"}, 500

# GET /anomalies
async def get_anomalies():
    logger.info("Fetching anomaly_detector results")

    if not os.path.exists(ANOMALY_FILE):
        return {"message": "No anomalies have been run yet"}, 404

    with open(ANOMALY_FILE, 'r') as f:
        return json.load(f), 200

app = connexion.FlaskApp(__name__, specification_dir=".")
app.add_api("anomaly.yml", base_path="/anomaly_detector", strict_validation=True, validate_responses=True)

if "CORS_ALLOW_ALL" in os.environ and os.environ["CORS_ALLOW_ALL"] == "yes":
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if __name__ == "__main__":
    logger.info("anomaly_detector Service started to find anomaly threshold is more than 1000")
    app.run(port=8130, host="0.0.0.0")
