# 🚀 Boot Sequence & Telemetry Guide

This document explains the **boot sequence** of the Plaid Bridge Open Banking API and the **telemetry traces** emitted into Redis during startup.  
It is designed for **operators and maintainers** who need cockpit‑grade visibility into the system’s health.

---

## 🔑 Key Concepts

- **Telemetry Keys** follow the schema:  

- **Values** are colon‑separated:  

- `value` → contextual payload (e.g., `success`, `failure`, `prefix:/api`)  
- `status` → machine‑readable state (`ok` or `error`)
- **TTLs**:  
- **60s (short)** → pulse signals for liveness  
- **300s (long)** → stability signals for core components

---

## 🛠 Boot Stages

### 1. Redis Initialization
- **Key**: `ttl:boot:complete:redis`  
- **Value**: `success:ok` (or `failure:error`)  
- **TTL**: 60s  
- Confirms whether the Redis client is connected.

### 2. Extensions
- **SQLAlchemy**  
- `ttl:boot:extension:sqlalchemy success:ok` (300s)  
- **Login Manager**  
- `ttl:boot:extension:login_manager success:ok` (60s)  
- **Limiter**  
- `ttl:boot:extension:limiter success:ok` (60s)  
- If Redis is unavailable: `disabled_no_redis:error`

### 3. Blueprints
- Each blueprint emits:  

Example:  
- `ttl:boot:blueprint:api_bp prefix:/api:ok` (300s)  
- Failures include the intended prefix:  
- `ttl:boot:blueprint:auth_bp failure:prefix:/auth:error`

- A summary trace confirms the registry ran:  
- `ttl:boot:complete:blueprints success:ok` (300s)

### 4. CLI Commands
- **Key**: `ttl:boot:cli:register`  
- **Value**: `success:ok` (or `failure:error`)  
- **TTL**: 300s  
- Confirms CLI commands (`audit`, `template_audit`) are wired.

### 5. Signals
- **Key**: `ttl:boot:complete:signals`  
- **Value**: `success:ok` (or `failure:error`)  
- **TTL**: 60s  
- Confirms schema listeners and other signals are wired.

### 6. Final App Boot
- **Key**: `ttl:boot:complete:app`  
- **Value**: `success:ok` (or enriched, e.g. `routes:128:ok`)  
- **TTL**: 60s  
- Confirms the application factory completed successfully.

---

## 📊 Operator Workflow

- **Check liveness**:  

Confirms Redis, signals, and app boot pulses.

- **Check stability**:  

Confirms all blueprints are registered and mounted.

- **Check CLI & extensions**:  


- **Interpret failures**:  
Any `failure:error` or `disabled_no_redis:error` indicates a degraded component.  
Missing keys after TTL expiry indicate the component has not refreshed its pulse.

---

## ✅ Summary

This boot sequence telemetry provides:
- **Narratability** → every stage of boot is explicit.  
- **Queryability** → operators can wildcard query Redis for a snapshot.  
- **Auditability** → failures are explicit, not inferred from silence.  
- **Resilience** → short TTLs for liveness, long TTLs for stability.

