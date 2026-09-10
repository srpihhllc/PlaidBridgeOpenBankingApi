A short summary of the 3‑tier sync loop

This project uses a 3‑tier sync loop to keep mobile clients, backend state, and external bank providers consistent and resilient.

- Tier 1 — Mobile / Client: the mobile app initiates syncs (manual or scheduled), applies deltas to a local cache, and acknowledges updates.
- Tier 2 — API / Sync Orchestrator: the Sync API persists requests, enqueues jobs, coordinates worker execution, deduplicates and enforces idempotency, and pushes notifications (push/webhook) back to clients.
- Tier 3 — Data Layer & Connectors: connector workers talk to third‑party providers (Plaid, TrueLayer, Basiq, Codat), normalize responses, persist normalized data and audit logs in the primary database.

Key properties
- Reliable: persistent job queue, worker retries with exponential backoff, rate‑limit handling for external providers.
- Idempotent: idempotency keys and dedupe logic prevent duplicated records on retries.
- Observable: audit log entries and job tracing for debugging and replay.
- Configurable: polling intervals, worker concurrency, and provider-specific timeouts are set via environment variables (SYNC_POLL_INTERVAL, WORKER_CONCURRENCY, CONNECTOR_TIMEOUT, NOTIFICATION_WEBHOOK_URL, etc.).

See the diagram (docs/3-tier-sync-loop.mmd) for a visual flow of the loop.