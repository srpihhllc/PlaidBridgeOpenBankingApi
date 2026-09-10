# Frontend Cockpit Topology (visual)

Below is a compact Mermaid diagram you can paste into a README to visualize the frontend ⇄ backend topology and OAuth flows.

```mermaid
flowchart LR
  subgraph FRONTEND
    A[RootLayout / App] --> B[(Tabs)]
    B --> Accounts[Accounts Screen]
    B --> Transactions[Transactions Screen]
    B --> Beneficiaries[Beneficiaries Screen]
    B --> Cards[Cards Screen]
    B --> Profile[Profile Screen]
    Plaid[Plaid Link UI] --> PlaidScript["cdn.plaid.com/link..."]
    OAuthCallback[OAuth Callback Screen]
  end

  subgraph BACKEND["mobile-app/server (dev) / API server"]
    TRPC[/api/trpc\n(tRPC httpBatchLink + superjson)/]
    REST_AUTH[/api/oauth/mobile\n/api/oauth/callback\n/api/auth/session\n/api/auth/me\n/api/auth/logout/]
    PLAID_ENDPOINTS[/api/generate_link_token\n/api/exchange_public_token/]
  end

  FRONTEND -- "tRPC (Bearer or Cookie)\nPOST /api/trpc" --> TRPC
  FRONTEND -- "REST fetch (credentials: include)\nGET /api/auth/me" --> REST_AUTH
  OAuthCallback -- "GET /api/oauth/mobile?code&state\n-> returns {app_session_id, user}" --> REST_AUTH
  FRONTEND -- "POST /api/auth/session (optional)\n(establish cookie from Bearer token)" --> REST_AUTH
  PlaidScript -- "loads external Plaid Link" --> Plaid
  FRONTEND -- "calls Plaid backend endpoints" --> PLAID_ENDPOINTS

  %% OAuth flows
  subgraph WebOAuth["Web flow"]
    User -->|login| Portal[OAUTH_PORTAL_URL]
    Portal -->|redirect code| REST_AUTH & OAuthCallback
    REST_AUTH -->|Set-Cookie| Browser
    Browser --> FRONTEND
  end

  subgraph MobileOAuth["Mobile / Native flow"]
    UserMobile -->|login| Portal
    Portal -->|deep link code| OAuthCallback
    OAuthCallback -->|GET /api/oauth/mobile| REST_AUTH
    REST_AUTH -->|JSON {app_session_id, user}| OAuthCallback
    OAuthCallback -->|store token| FRONTEND
  end
Code