# 📊 Telemetry Matrix

This document defines all cockpit‑grade telemetry emits across the application.

**Key schema:**


**Value schema:**


- **TTL_SHORT (60s)** → pulse / liveness
- **TTL_LONG (300s)** → stability / state confirmation

---

## 🔑 Boot Sequence

| Stage        | Key Pattern                          | Value Example(s)                              | Status   | TTL   | Notes |
|--------------|--------------------------------------|-----------------------------------------------|----------|-------|-------|
| Config load  | `ttl:boot:complete:config`           | `success:ok`                                  | ok       | 60s   | Config loaded successfully |
|              | `ttl:boot:error:config`              | `failure:ImportError…:error`                  | error    | 60s   | Config failure, aborts boot |
| Redis client | `ttl:boot:complete:redis`            | `success:ok`                                  | ok       | 60s   | Confirms Redis connectivity |
|              | `ttl:boot:error:redis`               | `failure:error`                               | error    | 60s   | No Redis available |
| SQLAlchemy   | `ttl:boot:extension:sqlalchemy`      | `success:ok` / `failure:…:error`              | ok/error | 300s  | Stability signal |
| LoginManager | `ttl:boot:extension:login_manager`   | `success:ok` / `failure:…:error`              | ok/error | 60s   | Pulse |
| Limiter      | `ttl:boot:extension:limiter`         | `success:ok` / `failure:…:error` / `failure:no_redis` | ok/error | 60s   | Disabled case emits `failure:no_redis` |
| Blueprints   | `ttl:boot:complete:blueprints`       | `count:{N}:ok`                                | ok       | 60s   | Summary count of registered blueprints |
| Blueprint audit | `ttl:boot:complete:blueprints:audit` | `{"expected":6,"actual":6,…}:ok`             | ok       | 300s  | JSON audit trace of blueprint health |
|              | `ttl:boot:error:blueprints:audit`    | `failure:redis:error`                         | error    | 300s  | Redis failure during audit emission |
| Per‑blueprint| `ttl:boot:blueprints:{bp_name}`      | `prefix:/api:ok` / `failure:/auth:error`      | ok/error | 300s  | Confirms each blueprint wiring |
| CLI commands | `ttl:boot:cli:register`              | `count:{N}:ok`                                | ok       | 300s  | Summary count of registered CLI commands |
| Signals      | `ttl:boot:complete:signals`          | `success:ok` / `failure:…:error`              | ok/error | 60s   | Confirms schema listeners wired |
| Final boot   | `ttl:boot:complete:app`              | `routes:{N}:blueprints:{M}:cli:{K}:ok`        | ok       | 60s   | Confirms app factory completed |

---

## 🛠 CLI & Migrations

| Stage            | Key Pattern                          | Value Example(s)                              | Status   | TTL   | Notes |
|------------------|--------------------------------------|-----------------------------------------------|----------|-------|-------|
| CLI summary      | `ttl:boot:cli:migrations`            | `success:ok`                                  | ok       | 300s  | Confirms migration commands wired |
| Hello command    | `ttl:cli:hello_command:run`          | `success:ok` / `failure:err:…`                | ok/error | 60s   | Example non‑migration command |
| Upgrade start    | `ttl:migration:upgrade:start`        | `from_rev:abc123:ok`                          | ok       | 60s   | Pulse at start of upgrade |
| Upgrade complete | `ttl:migration:upgrade:complete`     | `to_rev:def456:ok`                            | ok       | 300s  | Stability signal |
| Upgrade failure  | `ttl:migration:upgrade:failure`      | `from_rev:abc123:err:IntegrityError`          | error    | 300s  | Includes truncated error |
| Downgrade start  | `ttl:migration:downgrade:start`      | `from_rev:def456:to_rev:abc123:ok`            | ok       | 60s   | Pulse at start of downgrade |
| Downgrade done   | `ttl:migration:downgrade:complete`   | `to_rev:abc123:ok`                            | ok       | 300s  | Stability signal |
| Downgrade fail   | `ttl:migration:downgrade:failure`    | `from_rev:def456:err:…`                       | error    | 300s  | Includes truncated error |

---

## 🌐 Integrations

| Stage        | Key Pattern                          | Value Example(s) | Status   | TTL   | Notes |
|--------------|--------------------------------------|------------------|----------|-------|-------|
| Plaid        | `ttl:boot:integration:plaid_bp`      | `success:ok`     | ok       | 300s  | Plaid blueprint registered |
| Cockpit      | `ttl:boot:integration:cockpit_bp`    | `failure:error`  | error    | 300s  | Cockpit blueprint failed   |
| Celery       | `ttl:boot:integration:celery`        | `success:ok`     | ok       | 60s   | Confirms Celery worker up  |

---

## ✅ Operator Workflow

- **Check liveness**
  ```bash
  KEYS ttl:boot:complete:*

KEYS ttl:boot:extension:* ttl:boot:blueprints* ttl:boot:cli:*


---

This version folds in the **blueprint audit JSON**, **per‑blueprint emits**, and **integration keys**, while keeping the TTL semantics and naming consistent. It’s ready to paste into your repo’s `telemetry_matrix.md`.