# 🧱 Monorepo Architecture Diagram

This diagram represents the unified architecture of the Financial Powerhouse Platform.

Mobile App (Expo)
↓ TRPC
Shared TypeScript Server
↓ REST
Flask Backend API
↓ SQL
PostgreSQL + Drizzle + Alembic

Code

---

# 🧩 Notes

- TRPC provides type‑safe RPC between mobile and backend.  
- Drizzle schema ensures consistent relational modeling.  
- Alembic manages backend migrations.  
- All layers share a unified documentation and CI/CD pipeline.
