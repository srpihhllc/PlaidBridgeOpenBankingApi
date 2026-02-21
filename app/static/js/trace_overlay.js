// app/static/js/trace_overlay.js

/**
 * Cockpit Trace Overlay Renderer
 * Dynamically displays trace diagnostics, TTL freshness, and route health
 * across cockpit tiles and operator panels.
 */

document.addEventListener("DOMContentLoaded", function () {
  const traceMounts = document.querySelectorAll("[data-trace-key]");

  traceMounts.forEach(function (el) {
    const key = el.getAttribute("data-trace-key");

    fetch(`/api/trace/${key}`)
      .then((res) => res.json())
      .then((data) => {
        renderTTLOverlay(el, data);
      })
      .catch((err) => {
        el.innerHTML = `<span style="color:red">❌ Trace load failed for ${key}</span>`;
        console.error("Trace overlay error:", err);
      });
  });
});

/**
 * Renders TTL freshness bar and trace summary inline
 * @param {HTMLElement} el - DOM element
 * @param {Object} data - Trace payload
 */
function renderTTLOverlay(el, data) {
  const ttl = data.remaining_seconds;
  const fresh = data.fresh === "True";
  const color = fresh ? "#4CAF50" : "#F44336"; // green/red
  const barWidth = fresh ? `${Math.min(ttl, 300) / 3}%` : "100%";

  el.innerHTML = `
    <div style="font-weight:bold;">${data.label || data.key}</div>
    <div style="margin-top:4px; background:#eee; width:100%; height:6px; border-radius:3px;">
      <div style="height:6px; width:${barWidth}; background:${color}; border-radius:3px;"></div>
    </div>
    <div style="margin-top:4px; font-size:12px; color:#666;">Expires in ${ttl} sec</div>
  `;
}
