// File: static/js/stream.js
// Purpose: Client-side Server-Sent Events (SSE) stream handler.
// Competition Concept: Agent Skills (Interactive Web UI)

class TripForgeStream {
    constructor(streamUrl, logContainerId, statusSteps) {
        this.streamUrl = streamUrl;
        this.logContainer = document.getElementById(logContainerId);
        this.statusSteps = statusSteps; // Object mapping step numbers to DOM IDs
        this.eventSource = null;
        this.currentStep = 0;
    }

    start() {
        this.log("Initializing agent pipelines...");
        this.eventSource = new EventSource(this.streamUrl);

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (err) {
                this.log(`System: Error parsing stream packet: ${err}`, "text-red-400");
            }
        };

        this.eventSource.onerror = (err) => {
            this.log("System connection lost. Checking final compile state...", "text-yellow-400");
            this.stop();
            // Automatically attempt validation checks
            setTimeout(() => {
                window.location.href = "/result";
            }, 1500);
        };
    }

    handleEvent(data) {
        if (data.type === "progress") {
            const stepNum = data.step;
            const message = data.message;
            const status = data.status; // "done" or undefined (active)

            // Log update
            this.log(`[Agent Step ${stepNum}] ${message}`, status === "done" ? "text-green-400" : "text-blue-300");

            // Update status indicators in DOM
            this.updateStepUI(stepNum, status);
        } 
        else if (data.type === "complete") {
            this.log("Itinerary compiled! Redirecting to results...", "text-green-400 font-bold");
            this.stop();
            setTimeout(() => {
                window.location.href = "/result";
            }, 1000);
        } 
        else if (data.type === "error") {
            this.log(`Pipeline Error: ${data.message}`, "text-red-500 font-bold");
            this.stop();
            this.showErrorUI(data.message);
        }
    }

    updateStepUI(stepNum, status) {
        const stepId = this.statusSteps[stepNum];
        if (!stepId) return;

        const stepEl = document.getElementById(stepId);
        if (!stepEl) return;

        // Reset all classes
        stepEl.className = "flex items-center p-4 rounded-xl border border-gray-800 transition-all duration-300 ";

        const iconEl = stepEl.querySelector(".step-icon");
        const badgeEl = stepEl.querySelector(".step-badge");

        if (status === "done") {
            stepEl.classList.add("bg-green-950/20", "border-green-800/60");
            if (iconEl) iconEl.innerHTML = "✅";
            if (badgeEl) {
                badgeEl.innerHTML = "Completed";
                badgeEl.className = "step-badge text-xs px-2 py-0.5 rounded-full bg-green-900/40 text-green-300 border border-green-800/40";
            }
        } else {
            // Pulse active state
            stepEl.classList.add("step-active");
            if (iconEl) iconEl.classList.add("animate-bounce");
            if (badgeEl) {
                badgeEl.innerHTML = "Processing...";
                badgeEl.className = "step-badge text-xs px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-300 border border-blue-800/40 animate-pulse";
            }

            // Mark previous steps as done if we moved ahead
            for (let i = 1; i < stepNum; i++) {
                this.updateStepUI(i, "done");
            }
        }
    }

    log(message, textClass = "text-gray-300") {
        if (!this.logContainer) return;
        const entry = document.createElement("div");
        entry.className = `py-1 text-sm border-b border-gray-900/40 ${textClass}`;
        entry.innerHTML = `<span class="text-gray-500">[${new Date().toLocaleTimeString()}]</span> ${message}`;
        this.logContainer.appendChild(entry);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }

    showErrorUI(message) {
        const errorCard = document.getElementById("error-card");
        const errorMsg = document.getElementById("error-message");
        const loadingSection = document.getElementById("loading-section");
        
        if (loadingSection) loadingSection.classList.add("hidden");
        if (errorCard) {
            errorCard.classList.remove("hidden");
            if (errorMsg) errorMsg.innerText = message;
        }
    }

    stop() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}
window.TripForgeStream = TripForgeStream;
