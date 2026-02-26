---

# **AGENTS.md**  
### *Architecture & Operator Guide for the PlaidBridgeOpenBankingApi Monorepo*

---

# **1. Overview**

This monorepo contains the full **Financial Powerhouse Platform**, including:

- A hardened **Flask fintech API**  
- A full **React Native / Expo mobile banking app**  
- A complete **documentation suite** (MkDocs + GitHub Pages)  
- CI/CD workflows  
- Database migrations  
- Operator tools  
- Fraud detection, compliance scanning, and open banking integrations  

Copilot should use this file as **context**, not instructions.  
This document explains how the system works so Copilot can reason correctly across the entire repo.

---

# **2. Monorepo Structure**

```
PlaidBridgeOpenBankingApi/
│
├── PlaidBridgeOpenBankingApi/      # Flask backend (Python)
│   ├── app/
│   ├── migrations/
│   ├── .github/instructions/       # Modular Copilot rules
│   ├── AGENTS.md                   # This file
│   ├── run.py / wsgi.py
│   ├── requirements.txt
│   ├── alembic.ini
│   └── ...
│
├── mobile-app/                     # React Native / Expo mobile app
│   ├── app/
│   ├── components/
│   ├── constants/
│   ├── lib/
│   ├── drizzle/
│   ├── server/
│   ├── shared/
│   └── ...
│
├── docs/                           # MkDocs documentation suite
│   ├── 01-system-architecture.md
│   ├── 03-backend-architecture.md
│   ├── 12-mobile-architecture.md
│   ├── 09-api-reference.md
│   ├── 10-openapi.yaml
│   └── ...
│
├── .github/workflows/              # CI/CD
├── Makefile
├── README.md
└── ...
```

Copilot must understand that this is a **unified platform**, not separate projects.

---

# **3. Backend Architecture (Flask)**

The backend uses a hardened Flask architecture with:

- Application factory pattern  
- Centralized extension initialization  
- SQLAlchemy ORM  
- Flask-Migrate (Alembic)  
- JWT authentication  
- Redis-backed rate limiting  
- Structured logging  
- Operator‑visible telemetry  
- Fraud detection + compliance scanning  
- Plaid integration  

### **Key backend files**

```
PlaidBridgeOpenBankingApi/app/
    __init__.py          # create_app()
    extensions.py        # all Flask extensions
    models/              # SQLAlchemy models
    routes/              # API endpoints
    services/            # business logic
    utils/               # helpers
```

### **create_app() responsibilities**

- Load config  
- Initialize extensions  
- Register blueprints  
- Register CLI commands  
- Configure logging  
- Apply security headers  

### **init_extensions(app)** initializes:

- SQLAlchemy  
- Migrate  
- JWT  
- Redis client  
- Rate limiter  
- Mail  
- SocketIO  
- LoginManager  
- CSRF  

Copilot should **never bypass** `init_extensions(app)`.

---

# **4. Rate Limiting Logic**

The limiter is initialized via `_init_limiter(app, redis_enabled)`.

Rules:

- If `TESTING=True` → `_NoopLimiter`
- If `RATE_LIMIT_ENABLED=False` → `_NoopLimiter`
- If Redis available → real limiter
- If Redis fails → fallback to `_NoopLimiter`

Copilot must preserve this defensive behavior.

---

# **5. Models**

Models follow:

- SQLAlchemy declarative base  
- Naming conventions from `extensions.py`  
- Python 3.10+ typing  
- No circular imports  
- UUID or integer primary keys depending on domain  

Examples:

```
app/models/user.py
app/models/underwriter.py
app/models/revoked_token.py
```

---

# **6. Routes & Blueprints**

Routes live under:

```
app/routes/
```

Rules:

- Use Blueprints  
- Keep handlers thin  
- Business logic goes in `services/`  
- Validate input  
- Return JSON responses  

---

# **7. Services Layer**

Business logic lives in:

```
app/services/
```

Guidelines:

- No DB logic in routes  
- Keep services testable  
- Use dependency injection where possible  

---

# **8. Plaid Integration**

Flow:

1. Mobile app launches Plaid Link  
2. Receives `public_token`  
3. Sends to Flask: `/plaid/exchange`  
4. Flask exchanges for:
   - `access_token`
   - `item_id`
5. Flask stores tokens  
6. Mobile app fetches accounts + transactions via Flask  

Mobile app **never** talks directly to Plaid.

---

# **9. Fraud Detection & Compliance Engine**

Backend includes:

- AI-driven compliance scanning  
- Fraud detection  
- Account locking  
- Transaction monitoring  
- PDF statement parsing  
- Financial health scoring  

Copilot must preserve:

- operator visibility  
- narratable decisions  
- auditability  

---

# **10. Mobile App Architecture (React Native + Expo)**

The mobile app lives in:

```
mobile-app/
```

It uses:

- Expo Router  
- TypeScript  
- SecureStore for JWT  
- Fetch/Axios for API calls  
- Drizzle + SQLite for local storage  
- TRPC (optional local dev server)  

### **Mobile → Backend Communication**

Mobile app calls Flask via REST.

API base URL lives in:

```
mobile-app/constants/config.ts
```

Must use LAN IP, not localhost.

### **Authentication Flow**

1. Login → `/auth/login`  
2. Receive JWT  
3. Store in SecureStore  
4. Attach to all requests  
5. Backend validates + checks blocklist  

---

# **11. Documentation Suite**

Docs live in:

```
docs/
```

Includes:

- System architecture  
- Backend architecture  
- Mobile architecture  
- ERD  
- API reference  
- OpenAPI spec  
- CI/CD  
- Operator handbook  
- Release notes  

MkDocs deploys to GitHub Pages via:

```
.github/workflows/docs.yml
```

---

# **12. CI/CD**

CI/CD includes:

- Linting  
- Testing  
- Build  
- Docs deployment  
- Security checks  
- Operator workflows  

---

# **13. Developer Workflow**

- Use `/plan` for multi-file changes  
- Use `/delegate` for tangential tasks  
- Always run:
  - `ruff check .`
  - `black .`
  - `pytest -q`
- Follow conventional commits  
- Maintain cockpit-grade clarity in PRs  

---

# **14. Adding New Features**

1. Add Blueprint under `app/routes/`  
2. Add service logic under `app/services/`  
3. Add tests under `tests/`  
4. Update models if needed  
5. Generate migrations  
6. Update docs  
7. Update mobile app if endpoint affects UI  

---

# **15. Debugging Guidelines**

- Use structured logging  
- Validate environment variables  
- Check Redis connectivity  
- Use `pytest -q` to isolate failures  
- Use `/plan` for complex debugging  

---

# **End of AGENTS.md**

---
