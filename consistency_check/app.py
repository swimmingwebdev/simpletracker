import connexion
import os
import yaml
import json
import logging.config
from datetime import datetime, timezone
import asyncio
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

logger = logging.getLogger('consistencyLogger')

CHECKS_FILE = app_config["datastore"]
ANALYZER_URL = app_config["analyzer"]["url"]
STORAGE_URL = app_config["storage"]["url"]
PROCESSING_URL = app_config["processing"]["url"]

KAFKA_HOSTNAME = app_config["events"]["hostname"]
KAFKA_PORT = app_config["events"]["port"]
KAFKA_TOPIC = app_config["events"]["topic"]

logger.info(f"Kafka config - Host: {KAFKA_HOSTNAME}, Port: {KAFKA_PORT}, Topic: {KAFKA_TOPIC}")

# Initialize or load previous results
def load_results():
    if os.path.exists(CHECKS_FILE):
        with open(CHECKS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save new check result
def save_results(data):
    with open(CHECKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Helper: match events based on device_id + timestamp + trace_id
def event_key(event):
    return (event.get("device_id"), event.get("timestamp"), event.get("trace_id"))

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

# POST /update
async def run_consistency_checks():
    logger.info("Running consistency check")
    start_time = datetime.now()

    try:
        now = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient() as client:
            analyzer_stats = (await client.get(f"{ANALYZER_URL}/stats")).json()
            storage_stats = (await client.get(f"{STORAGE_URL}/stats")).json()
            processing_stats = (await client.get(f"{PROCESSING_URL}/stats")).json()

        # Access all DB event IDs from storage
        async with httpx.AsyncClient() as client:
            gps_db = (await client.get(f"{STORAGE_URL}/track/locations", params={
                "start_timestamp": "2000-01-01T00:00:00Z", "end_timestamp": now
            })).json()
            alerts_db = (await client.get(f"{STORAGE_URL}/track/alerts", params={
                "start_timestamp": "2000-01-01T00:00:00Z", "end_timestamp": now
            })).json()

        # Access all queue event IDs from analyzer
        gps_queue = await fetch_all_analyzer_events(ANALYZER_URL, "locations")
        alerts_queue = await fetch_all_analyzer_events(ANALYZER_URL, "alerts")

        # Compare for mismatches
        all_db = {event_key(e): e for e in gps_db + alerts_db}
        all_queue = {event_key(e): e for e in gps_queue + alerts_queue}

        not_in_db = [v for k, v in all_queue.items() if k not in all_db]
        not_in_queue = [v for k, v in all_db.items() if k not in all_queue]

        # Save results
        result = {
            "last_updated": now,
            "counts": {
                "db": {
                    "gps": len(gps_db),
                    "alerts": len(alerts_db)
                },
                "queue": {
                    "gps": len(gps_queue),
                    "alerts": len(alerts_queue)
                },
                "processing": {
                    "gps": processing_stats.get("num_gps_events", 0),
                    "alerts": processing_stats.get("num_alert_events", 0)
                }
            },
            "not_in_db": not_in_db,
            "not_in_queue": not_in_queue
        }

        save_results(result)

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return {"processing_time_ms": processing_time}, 200

    except Exception as e:
        logger.error(f"Error during consistency check: {str(e)}")
        return {"message": "Error during consistency check"}, 500

# GET /checks
async def get_checks():
    logger.info("Fetching consistency check results")

    if not os.path.exists(CHECKS_FILE):
        return {"message": "No checks have been run yet"}, 404

    with open(CHECKS_FILE, 'r') as f:
        return json.load(f), 200

app = connexion.FlaskApp(__name__, specification_dir=".")
app.add_api("openapi.yml", base_path="/consistency", strict_validation=True, validate_responses=True)

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
    logger.info("Consistency Check Service started")
    app.run(port=8120, host="0.0.0.0")
