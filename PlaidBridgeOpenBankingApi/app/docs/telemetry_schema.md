# 📡 Cockpit‑Grade Telemetry Schema

This schema defines a **uniform, operator‑visible pattern** for all Time‑to‑Live (TTL) traces emitted into Redis. By enforcing this structure, every boot event, blueprint registration, CLI command, and integration state becomes **narratable, queryable, and auditable**.

---

## 🔑 Key Structure

All telemetry keys follow a **dot‑separated hierarchy**:


- **domain** → Logical component (e.g., `boot`, `cli`, `blueprint`, `integration`, `extension`, `migration`).
- **event** → Action or state (e.g., `complete`, `error`, `registration`).
- **detail** → Unique identifier (e.g., `app`, `plaid_bp`, `sqlalchemy`, `audit`).

---

## 📦 Value Structure

Each Redis value is a **colon‑separated string**:


- **value** → Contextual payload (e.g., `success`, `failure`, `prefix:/api`, `revision:20250924`).
- **status** → Machine‑readable state (`ok` or `error`).

Values are stored as **bytes** (`utf‑8` encoded).

---

## ⏱ TTL Semantics

Two TTL classes provide both **pulse** and **stability** signals:

- **Short‑lived (60s)** → Real‑time liveness checks (e.g., app boot complete, Redis connected).
- **Long‑lived (300s)** → Stability confirmations (e.g., blueprint registration, CLI wiring).

---

## 📖 Examples

### 1. App Boot Events
| Key                          | Value        | TTL  | Purpose |
|-------------------------------|--------------|------|---------|
| `ttl:boot:complete:app`       | `success:ok` | 60s  | Confirms the Flask app has fully started |
| `ttl:boot:complete:signals`   | `success:ok` | 60s  | Confirms signal listeners are wired |
| `ttl:boot:error:signals`      | `failure:error` | 60s | Indicates a signal wiring failure |
| `ttl:boot:complete:redis`     | `success:ok` | 60s  | Confirms Redis client is connected |
| `ttl:boot:error:redis`        | `failure:error` | 60s | Redis connection failure |

---

### 2. Blueprint Registration
| Key                                | Value              | TTL  | Purpose |
|------------------------------------|--------------------|------|---------|
| `ttl:boot:blueprint:main_bp`       | `prefix:/:ok`      | 300s | Confirms `main_bp` registered at `/` |
| `ttl:boot:blueprint:api_bp`        | `prefix:/api:ok`   | 300s | Confirms `api_bp` registered at `/api` |
| `ttl:boot:blueprint:letter_bp`     | `prefix:/api:ok`   | 300s | Confirms `letter_bp` registered at `/api` |
| `ttl:boot:blueprint:auth_bp`       | `failure:prefix:/auth:error` | 300s | Shows a failure for `auth_bp` |

---

### 3. Optional Integrations
| Key                                   | Value        | TTL  | Purpose |
|---------------------------------------|--------------|------|---------|
| `ttl:boot:integration:plaid_bp`       | `success:ok` | 300s | Plaid blueprint registered successfully |
| `ttl:boot:integration:cockpit_bp`     | `failure:error` | 300s | Cockpit blueprint failed to register |
| `ttl:boot:integration:celery`         | `success:ok` | 60s  | Confirms Celery worker is up |

---

### 4. CLI Commands
| Key                               | Value        | TTL  | Purpose |
|-----------------------------------|--------------|------|---------|
| `ttl:boot:cli:audit`              | `success:ok` | 300s | Confirms `audit` CLI command registered |
| `ttl:boot:cli:template_audit`     | `success:ok` | 300s | Confirms `template_audit` CLI command registered |
| `ttl:boot:cli:register`           | `failure:error` | 300s | CLI registration failure |

---

### 5. Extensions
| Key                                   | Value        | TTL  | Purpose |
|---------------------------------------|--------------|------|---------|
| `ttl:boot:extension:sqlalchemy`       | `success:ok` | 60s  | SQLAlchemy initialized |
| `ttl:boot:extension:redis`            | `failure:error` | 60s | Redis extension failed |
| `ttl:boot:extension:login_manager`    | `success:ok` | 60s  | LoginManager initialized |

---

### 6. Migrations
| Key                                         | Value              | TTL  | Purpose |
|---------------------------------------------|--------------------|------|---------|
| `ttl:boot:migration:revision_20250924`      | `success:ok`       | 300s | Migration applied successfully |
| `ttl:boot:migration:revision_20250924`      | `failure:error`    | 300s | Migration failed |

---

## 🛠 Implementation Helper

To enforce schema consistency, wrap your `ttl_emit`:

```python
def emit_boot_trace(domain: str, event: str, detail: str, value: str, status: str, ttl: int, client):
    """
    Emit a cockpit-grade TTL trace into Redis.
    """
    if not client:
        return
    key = f"ttl:{domain}:{event}:{detail}"
    payload = f"{value}:{status}".encode("utf-8")
    client.setex(key, ttl, payload)


---

This is copy‑paste ready. It gives you a **single, authoritative schema doc** for your repo.  

Do you want me to also **refactor your existing `ttl_emit` helper** so it enforces this schema automatically (instead of manually formatting keys/values in each call)?