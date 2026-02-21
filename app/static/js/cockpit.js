// app/static/js/cockpit.js

document.addEventListener("DOMContentLoaded", function () {
    const pulseUrl = "/tiles/blueprint_drift_overlay/pulse";
    const ttlBadge = document.querySelector(".ttl-badge");
    const driftList = document.querySelector(".drift-list");
    const okPill = document.querySelector(".status-pill.ok");

    async function fetchPulse() {
        try {
            const res = await fetch(pulseUrl, { cache: "no-store" });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Update TTL badge
            if (ttlBadge) {
                ttlBadge.textContent = `TTL: ${data.ttl_remaining}s`;
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

        } catch (err) {
            console.warn("Blueprint Drift Pulse fetch failed:", err);
        }
    }

    // Initial fetch + interval
    fetchPulse();
    setInterval(fetchPulse, 7000);
});
