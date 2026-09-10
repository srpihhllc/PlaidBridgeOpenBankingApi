// app/static/js/cockpit.js

document.addEventListener("DOMContentLoaded", function () {
    const pulseUrl = "/tiles/blueprint_drift_overlay/pulse";
    const ttlBadge = document.querySelector(".ttl-badge");
    const driftList = document.querySelector(".drift-list");
    const okPill = document.querySelector(".status-pill.ok");

    let errorCount = 0;
    const MAX_ERRORS = 5;

    async function fetchPulse() {
        // 1. Circuit Breaker: Stop hammering the server if it's dead
        if (errorCount >= MAX_ERRORS) {
            console.error(`Blueprint drift pulse suspended after ${MAX_ERRORS} consecutive failures.`);
            if (ttlBadge) {
                ttlBadge.textContent = "TTL: ERR";
                ttlBadge.classList.add("ttl-fail");
            }
            return; 
        }

        try {
            const res = await fetch(pulseUrl, { cache: "no-store" });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Reset error count on successful fetch
            errorCount = 0;

            // Update TTL badge
            if (ttlBadge) {
                // Defensive check in case the dummy route doesn't have ttl_remaining yet
                const ttl = data.ttl_remaining !== undefined ? data.ttl_remaining : "N/A";
                ttlBadge.textContent = `TTL: ${ttl}s`;
                ttlBadge.classList.remove("ttl-ok", "ttl-fail");
                ttlBadge.classList.add(data.status === "fail" ? "ttl-fail" : "ttl-ok");
            }

            // Update drift list or OK pill
            if (data.status === "fail" && Array.isArray(data.failures) && driftList) {
                driftList.innerHTML = "";
                data.failures.forEach(f => {
                    const li = document.createElement("li");
                    const a = document.createElement("a");
                    a.href = f.link || "#";
                    a.className = "status-pill fail";
                    a.title = `Open ${f.name} at line ${f.line}`;
                    a.innerHTML = `
                        <span class="pill-label">${f.name}</span>
                        <span class="pill-meta">line ${f.line}</span>
                    `;
                    li.appendChild(a);
                    driftList.appendChild(li);
                });
                if (okPill) okPill.style.display = "none";
            } else if (data.status === "ok" && okPill) {
                okPill.innerHTML = `<span class="pill-label">✅ No blueprint drift detected</span>`;
                okPill.style.display = "inline-block";
                if (driftList) driftList.innerHTML = "";
            }

            // 2. Recursive Scheduling: Only queue the next request AFTER this one succeeds
            setTimeout(fetchPulse, 7000);

        } catch (err) {
            errorCount++;
            console.warn(`Blueprint Drift Pulse fetch failed (${errorCount}/${MAX_ERRORS}):`, err);
            
            // Queue a retry, but it will abort at the top of the function once MAX_ERRORS is hit
            setTimeout(fetchPulse, 7000);
        }
    }

    // Initial fetch starts the cycle
    fetchPulse();
});