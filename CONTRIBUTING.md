# 🤝 Contributing to Financial Powerhouse API

We welcome cockpit‑grade contributions! This project enforces **operator‑visible reliability, maintainability, and transparency**. Please follow these guidelines to keep the system narratable and future‑proof.

---

## 🛠 Development Workflow

1. **Fork & Branch**
   - Fork the repo and create a feature branch from `main`.
   - Use descriptive branch names: `feature/redis-ssl-helper`, `fix/migration-drift`.

2. **Pre‑commit Hooks**
   - Run `make lint` and `make typecheck` locally before committing.
   - Lockfile drift is enforced — run `make update` if requirements change.

3. **Commit Messages**
   - Use clear, narratable messages:
     ```
     feat: add deterministic FK naming to Alembic migrations
     fix: enforce SSL in Redis helper
     docs: update operator runbook for fraud detection
     ```

---

## 🧪 Testing & Coverage

- Use pytest markers (`fast`, `redis`, `plaid`, `providers`, `infra`) to segment tests.
- Ensure coverage stays above **85%**.
- Run:
  ```bash
  make test

