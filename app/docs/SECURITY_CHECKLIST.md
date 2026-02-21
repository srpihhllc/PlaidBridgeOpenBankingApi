# 🔒 FinBrain Cortex — Security & Form Hygiene Checklist

This checklist ensures all templates remain **bulletproof** against CSRF leaks, layout breakage, and onboarding ambiguity.

---

## ✅ Templates with POST Forms (must include hidden CSRF input)

- **auth/login.html**  
  - [x] Hidden CSRF input  
  - [x] `text-break` on alerts  
  - [x] Optional `next` redirect supported  

- **auth/login_subscriber.html**  
  - [x] Hidden CSRF input  
  - [x] Subscriber‑specific labels and copy  

- **auth/register_subscriber.html**  
  - [x] Hidden CSRF input  
  - [x] Username + email + password fields  

- **auth/update_password.html**  
  - [x] Hidden CSRF input  
  - [x] Client‑side password match validation  
  - [x] `text-break` on alerts  

- **auth/mfa_prompt.html**  
  - [x] Hidden CSRF input  
  - [x] Autofocus on MFA code  
  - [x] `text-break` on alerts  

- **auth/forgot_password.html**  
  - [x] Hidden CSRF input  
  - [x] Tailwind/Bootstrap hybrid styling  
  - [x] Flash messages styled consistently  

- **admin/operator_login.html**  
  - [x] Hidden CSRF input (corrected)  
  - [x] `text-break` on alerts  
  - [x] Optional `next` redirect supported  

---

## ✅ Templates without POST Forms (no CSRF needed)

- **auth/me.html**  
  - Display‑only (links to update password/logout).  
  - No CSRF required.  

- **auth/identity_events.html**  
  - Filter form is GET only.  
  - No CSRF required.  

---

## 🔧 Hygiene Standards

- All POST forms: **hidden CSRF input**  
- All flash messages: **`text-break`** to prevent overflow  
- All inputs: **labels bound to IDs** for accessibility  
- All buttons: **`aria-label`** where needed  
- Routes: **consistent wiring** (`auth.login`, `auth.register_subscriber`, etc.)  
- Optional redirect (`next`): present where appropriate  

---

## 🚀 Verdict

All templates are now **CSRF‑protected, operator‑friendly, and narratable**.  
Future maintainers: **never add a POST form without a hidden CSRF input** and always wrap flash messages with `text-break`.

