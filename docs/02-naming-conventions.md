# 🏷 Naming Conventions

The platform uses a dual‑identity naming model to separate technical and product concerns.

---

## 1. Technical Identity — `PlaidBridgeOpenBankingApi`

Used for:

- GitHub repository  
- Backend API service  
- Python package  
- Docker images  
- CI/CD workflows  
- Internal architecture diagrams  
- Deployment artifacts  
- Import paths  

This identity reflects the underlying open banking API implementation.

---

## 2. Product Identity — **Financial Powerhouse Platform**

Used for:

- Documentation  
- Platform overview  
- Developer onboarding  
- Operator handbook  
- Release notes  
- Mobile app UX  
- Public‑facing architecture diagrams  

This identity reflects the full end‑to‑end fintech platform.

---

## 3. Why Two Names?

This separation mirrors industry best practices (Stripe, Plaid, AWS, Firebase) and ensures:

- Technical clarity  
- Product clarity  
- Zero breaking changes  
- Clean onboarding for future maintainers  
- Consistent documentation  
- Stable API identity  

---

## 4. Summary

| Context | Name |
|--------|------|
| Repo / API / Code | `PlaidBridgeOpenBankingApi` |
| Platform / Docs / UX | Financial Powerhouse Platform |

Both identities are correct — they serve different layers of the system.
