/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const CLOUD_VM_DNS = "34.234.232.11" 
const PROCESSING_STATS_API = `http://${CLOUD_VM_DNS}/processing/stats`
const ANALYZER_API = {
    stats: `http://${CLOUD_VM_DNS}/analyzer/stats`,
    trackGPS: `http://${CLOUD_VM_DNS}/analyzer/track/locations`,
    trackAlerts: `http://${CLOUD_VM_DNS}/analyzer/track/alerts`
}
const CONSISTENCY_CHECK_API = `http://${CLOUD_VM_DNS}/consistency_check/update`

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
    document.getElementById("consistency-form").addEventListener("submit", (e) => {
        e.preventDefault();

        fetch(CONSISTENCY_CHECK_API, {
            method: "POST"
        })
        .then(res => res.json())
        .then(data => {
            const resultElem = document.getElementById("consistency-result");
            resultElem.innerText = `Consistency Check Completed.\nProcessing Time: ${data.processing_time_ms} ms`;
        })
        .catch(err => {
            document.getElementById("consistency-result").innerText = "Error running consistency check.";
            console.error(err);
        });
    });
}

document.addEventListener('DOMContentLoaded', setup)