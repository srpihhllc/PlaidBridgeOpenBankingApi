# 🏗 Backend Architecture — Financial Powerhouse Platform

The backend is the core enforcement engine of the Financial Powerhouse Platform.  
It handles compliance, fraud detection, smart contract simulation, financial scoring, PDF ingestion, and open banking integrations.

---

# ⚙️ Technology Stack

- **Flask** — REST API framework  
- **SQLAlchemy ORM** — relational modeling  
- **Alembic** — schema migrations  
- **Redis** — rate limiting, telemetry, TTL traces  
- **JWT Authentication** — via flask‑jwt‑extended  
- **pdfplumber** — PDF statement parsing  
- **Plaid API** — account linking + transactions  
- **Treasury Prime** — banking operations  

---

# 🧩 High‑Level Architecture

Client → Flask API → Services → SQLAlchemy → PostgreSQL
│
└── Redis (rate limits, telemetry)

Code

---

# 📂 Directory Structure

app/
├── init.py
├── config.py
├── models.py
├── routes/
├── services/
├── migrations/
└── tests/

Code

---

# 🚦 Core Responsibilities

### **Compliance Engine**
- AI‑driven agreement scanning  
- Auto‑lock on repeated violations  

### **Fraud Detection**
- Transaction anomaly detection  
- Auto‑lock on suspicious activity  

### **Smart Contract Simulation**
- Deterministic execution  
- Event‑driven state transitions  

### **Financial Health Scoring**
- Transaction‑based scoring  
- Risk modeling  

### **Open Banking**
- Plaid OAuth  
- Transaction ingestion  
- PDF → transaction extraction  

---

# 🔐 Security Model

- JWT authentication  
- SECRET_KEY rotation  
- Rate limiting via Redis  
- Admin seed validation  
- Strict FK integrity  

---

# 🧪 Testing Strategy

- 100% coverage enforced  
- CI smoke tests validate:
  - admin seed  
  - 27 FK relationships  
  - cross‑table integrity  

---

# 📡 Telemetry

- Redis TTL traces  
- Rate‑limit counters  
- `/health` endpoint  
- Audit logs for compliance + fraud  

---

# 📚 Related Documentation

- Database ERD — `04-database-erd.md`  
- CI/CD Pipeline — `06-ci-cd-pipeline.md`  
- Operator Handbook — `07-operator-handbook.md`  
- API Reference — `09-api-reference.md`  
- OpenAPI Spec — `10-openapi.yaml`  
