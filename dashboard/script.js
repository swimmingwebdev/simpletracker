/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const CLOUD_VM_DNS = "34.234.232.11" 
const PROCESSING_STATS_API = `http://${CLOUD_VM_DNS}/processing/stats`
const ANALYZER_API = {
    stats: `http://${CLOUD_VM_DNS}/analyzer/stats`,
    trackGPS: `http://${CLOUD_VM_DNS}/analyzer/track/locations`,
    trackAlerts: `http://${CLOUD_VM_DNS}/analyzer/track/alerts`
}
const CONSISTENCY_CHECK_API = `http://${CLOUD_VM_DNS}/consistency_check/checks`

// This function fetches and updates the general statistics
const makeReq = (url, cb) => {
    fetch(url)
        .then(res => res.json())
        .then((result) => {
            console.log("Received data: ", result)
            cb(result);
        }).catch((error) => {
            updateErrorMessages(error.message)
        })
}

const updateCodeDiv = (result, elemId) => {
    const elem = document.getElementById(elemId);
    if (!elem) return;
    
    // For statistics, display in simple format
    if (typeof result === 'object') {
        let text = '';
        for (const [key, value] of Object.entries(result)) {
            text += `${key}: ${value}\n`;
        }
        elem.innerText = text;
    } else {
        elem.innerText = result;
    }
}

const getLocaleDateStr = () => (new Date()).toLocaleString()

const getStats = () => {
    document.getElementById("last-updated-value").innerText = getLocaleDateStr()
    
    // makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"))
    // makeReq(ANALYZER_API_URL.stats, (result) => updateCodeDiv(result, "analyzer-stats"))
    // makeReq(ANALYZER_API_URL.snow, (result) => updateCodeDiv(result, "event-snow"))
    // makeReq(ANALYZER_API_URL.lift, (result) => updateCodeDiv(result, "event-lift"))

    makeReq(PROCESSING_STATS_API, (result) => {
        // Format processing stats for better display
        let formattedStats = {
            "Number of GPS Events Stored": result.num_gps_events || 0,
            "Number of Alert Events Stored": result.num_alert_events || 0,
            "Max Alerts Per Day": result.max_alerts_per_day || "N/A",
            "Peak GPS Activity Day": result.peak_gps_activity_day || "N/A",
            "Last Updated": result.last_updated ? new Date(result.last_updated).toLocaleString() : "N/A"
        }
        updateCodeDiv(formattedStats, "processing-stats")
    })
    
    // Fetch analyzer stats
    makeReq(ANALYZER_API.stats, (result) => {
        // Format analyzer stats for better display
        let formattedStats = {
            "GPS Events Count": result.num_gps_events || 0,
            "Alert Events Count": result.num_alert_events || 0
        }
        updateCodeDiv(formattedStats, "analyzer-stats")
    })
}

const fetchGpsEvent = () => {
    const index = document.getElementById("gps-index").value;
    fetch(`${ANALYZER_API.trackGPS}?index=${index}`)
        .then(res => res.json())
        .then(data => {
            // document.getElementById("event-gps").innerText = JSON.stringify(data, null, 2);
            let eventText = '';
            for (const [key, value] of Object.entries(data)) {
                eventText += `${key}: ${value}\n`;
            }
            document.getElementById("event-gps").innerText = eventText;
        })
        .catch(err => {
            document.getElementById("event-gps").innerText = "Error fetching GPS event";
            console.error(err);
        });
};

const fetchAlertEvent = () => {
    const index = document.getElementById("alert-index").value;
    fetch(`${ANALYZER_API.trackAlerts}?index=${index}`)
        .then(res => res.json())
        .then(data => {
            // document.getElementById("event-alert").innerText = JSON.stringify(data, null, 2);
            let eventText = '';
            for (const [key, value] of Object.entries(data)) {
                eventText += `${key}: ${value}\n`;
            }
            document.getElementById("event-alert").innerText = eventText;
        })
        .catch(err => {
            document.getElementById("event-alert").innerText = "Error fetching Alert event";
            console.error(err);
        });
};

const fetchConsistencyCheck = (e) => {

    e.preventDefault();

    const resultElem = document.getElementById("consistency-result");
    resultElem.innerText = "Running consistency check...";

    fetch(CONSISTENCY_CHECK_API)
        .then(res => res.json())
        .then(data => {

            let results = "Consistency Check Results:\n\n";

            results += "MySQL Database:\n";
            results += `  Alerts: ${data.counts.db.alerts}\n`;
            results += `  GPS: ${data.counts.db.gps}\n\n`;
            
            results += "Queue in Kafka:\n";
            results += `  Alerts: ${data.counts.queue.alerts}\n`;
            results += `  GPS: ${data.counts.queue.gps}\n\n`;

            results += "Processing Service:\n";
            results += `  Alerts: ${data.counts.processing.alerts}\n`;
            results += `  GPS: ${data.counts.processing.gps}\n\n`;

            // Compare database vs queue
            const dbQueueAlertDiff = data.counts.db.alerts - data.counts.queue.alerts;
            const dbQueueGpsDiff = data.counts.db.gps - data.counts.queue.gps;
            
            results += "Database vs Queue:\n";
            results += `  Alerts: ${dbQueueAlertDiff > 0 ? '+' : ''}${dbQueueAlertDiff}\n`;
            results += `  GPS: ${dbQueueGpsDiff > 0 ? '+' : ''}${dbQueueGpsDiff}\n\n`;

            results += "Database vs Processing:\n";
            results += `  Alerts: ${dbProcessingAlertDiff > 0 ? '+' : ''}${dbProcessingAlertDiff}\n`;
            results += `  GPS: ${dbProcessingGpsDiff > 0 ? '+' : ''}${dbProcessingGpsDiff}\n\n`;

            results += "Missing events:\n";
            // Events not in db
            const notInDbCount = data.not_in_db ? data.not_in_db.length : 0;
            results += `Events in queue but not in database: ${notInDbCount}\n`;
            
            // Events not in queue
            const notInQueueCount = data.not_in_queue ? data.not_in_queue.length : 0;
            results += `Events in database but not in queue: ${notInQueueCount}\n\n`;
            
            results += `Processing Time: ${data.processing_time_ms} ms\n`;

            results += `Last checked: ${data.last_updated}`;
            
            resultElem.innerText = results;
        })
        .catch(err => {
            resultElem.innerText = "Error running consistency check: " + err.message;
            console.error(err);
        });
}

const updateErrorMessages = (message) => {
    const id = Date.now()
    console.log("Creation", id)

    const msg = document.createElement("div")
    msg.id = `error-${id}`
    msg.innerHTML = `<p>Something happened at ${getLocaleDateStr()}!</p><code>${message}</code>`
    document.getElementById("messages").style.display = "block"
    document.getElementById("messages").prepend(msg)
    setTimeout(() => {
        const elem = document.getElementById(`error-${id}`)
        if (elem) { elem.remove() }
    }, 7000)
}

const setup = () => {
    getStats()
    setInterval(() => getStats(), 4000) // Update every 4 seconds

    document.getElementById("fetch-gps-btn").addEventListener("click", fetchGpsEvent);
    document.getElementById("fetch-alert-btn").addEventListener("click", fetchAlertEvent);

    //consistency_check button
    document.getElementById("consistency-form").addEventListener("submit", fetchConsistencyCheck);
}

document.addEventListener('DOMContentLoaded', setup)