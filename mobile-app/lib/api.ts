import { getApiBaseUrl, PLATFORM_CONFIG } from "@/constants/oauth";

import * as Auth from "@/lib/auth";



export interface FintechAccount {

  id: number;

  accountName: string;

  accountType: string;

  accountNumber: string;

  balance: string;

  currency: string;

  status: "active" | "frozen" | "closed";

}



export interface FintechCard {

  id: number;

  cardBrand: string;

  cardNumber: string;

  holderName: string;

  expiryDate: string;

  status: "active" | "blocked" | "expired";

}



export interface FintechTransaction {

  id: number;

  transactionType: "transfer" | "deposit" | "withdrawal" | "payment" | "recharge";

  amount: string;

  recipientName?: string;

  description?: string;

  status: "pending" | "completed" | "failed" | "cancelled";

  createdAt: string;

}



export async function apiCall<T>(endpoint: string, options: RequestInit = {}): Promise<T> {

  const headers: Record<string, string> = {

    "Content-Type": "application/json",

    ...((options.headers as Record<string, string>) || {}),

  };



  const sessionToken = await Auth.getSessionToken();

  if (sessionToken) {

    headers["Authorization"] = `Bearer ${sessionToken}`;

  }



  const baseUrl = getApiBaseUrl();

  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  const url = baseUrl ? `${baseUrl}${cleanEndpoint}` : cleanEndpoint;



  const response = await fetch(url, {

    ...options,

    headers,

    credentials: "include",

  });



  if (!response.ok) {

    const errorText = await response.text();

    let errorMessage = errorText;

    try {

      const errorJson = JSON.parse(errorText);

      errorMessage = errorJson.error || errorJson.message || errorJson.msg || errorText;

    } catch {

      // keep raw text

    }

    throw new Error(errorMessage || `API call failed: ${response.statusText}`);

  }



  const contentType = response.headers.get("content-type");

  if (contentType && contentType.includes("application/json")) {

    return (await response.json()) as T;

  }



  const text = await response.text();

  return (text ? JSON.parse(text) : {}) as T;

}



export async function loginWithPassword(

  email: string,

  password: string,

): Promise<{ access_token: string; refresh_token?: string; user?: any }> {

  const result = await apiCall<{ access_token: string; refresh_token?: string; user?: any }>(

    PLATFORM_CONFIG.endpoints.auth.login,

    {

      method: "POST",

      body: JSON.stringify({ email, password }),

    },

  );

  if (result.access_token) {

    await Auth.setSessionToken(result.access_token);

  }

  if (result.user) {

    await Auth.setUserInfo(result.user);

  }

  return result;

}



export async function logout(): Promise<void> {

  try {

    await apiCall<void>(PLATFORM_CONFIG.endpoints.auth.logout, { method: "POST" });

  } finally {

    await Auth.removeSessionToken();

    await Auth.clearUserInfo();

  }

}



export async function getMe(): Promise<{

  id: number;

  openId: string;

  name: string | null;

  email: string | null;

  loginMethod: string | null;

  lastSignedIn: string;

} | null> {

  try {

    const result = await apiCall<{ user?: any; data?: any }>(PLATFORM_CONFIG.endpoints.auth.me);

    const u = result.user || result.data || result;

    if (!u || !u.id) return null;

    return {

      id: Number(u.id),

      openId: String(u.id),

      name: u.username || u.name || u.email || null,

      email: u.email || null,

      loginMethod: "jwt",

      lastSignedIn: new Date().toISOString(),

    };

  } catch {

    return null;

  }

}



export async function fetchAccounts(): Promise<FintechAccount[]> {

  const res = await apiCall<{ accounts?: FintechAccount[] }>(

    PLATFORM_CONFIG.endpoints.banking.accounts,

  );

  return res.accounts ?? [];

}



export async function fetchCards(): Promise<FintechCard[]> {

  const res = await apiCall<{ cards?: FintechCard[] }>(

    PLATFORM_CONFIG.endpoints.banking.cards,

  );

  return res.cards ?? [];

}



export async function fetchTransactions(limit = 50): Promise<FintechTransaction[]> {

  const res = await apiCall<{ transactions?: FintechTransaction[] }>(

    `${PLATFORM_CONFIG.endpoints.banking.transactions}?limit=${limit}`,

  );

  return res.transactions ?? [];

}



export async function createTransfer(payload: {

  accountId?: number;

  recipientName: string;

  recipientAccount: string;

  amount: string;

  description?: string;

}): Promise<FintechTransaction> {

  const res = await apiCall<{ transaction: FintechTransaction }>(

    PLATFORM_CONFIG.endpoints.banking.transfers,

    {

      method: "POST",

      body: JSON.stringify(payload),

    },

  );

  return res.transaction;

}



export async function signShieldDisclosure(payload: {

  agreement_id: number;

  signature: string;

  accepted_rules?: boolean;

}): Promise<Record<string, unknown>> {

  return apiCall<Record<string, unknown>>(PLATFORM_CONFIG.endpoints.shield.signDisclosure, {

    method: "POST",

    body: JSON.stringify({ accepted_rules: true, ...payload }),

  });

}



export async function fetchScopedProxySnapshot(

  lenderId: number,

  borrowerId: string,

): Promise<Record<string, unknown>> {

  return apiCall<Record<string, unknown>>(PLATFORM_CONFIG.endpoints.shield.scopedProxySnapshot, {

    method: "POST",

    body: JSON.stringify({ lender_id: lenderId, borrower_id: borrowerId }),

  });

}



export async function createPlaidLinkToken(): Promise<{ link_token: string }> {

  return apiCall<{ link_token: string }>(PLATFORM_CONFIG.endpoints.plaid.createLinkToken, {

    method: "POST",

  });

}



export async function exchangePlaidPublicToken(

  publicToken: string,

  metadata?: Record<string, unknown>,

): Promise<Record<string, unknown>> {

  return apiCall<Record<string, unknown>>(PLATFORM_CONFIG.endpoints.plaid.exchangePublicToken, {

    method: "POST",

    body: JSON.stringify({ public_token: publicToken, metadata }),

  });

}



export async function fetchAccountSnapshot(): Promise<Record<string, unknown>> {

  return apiCall<Record<string, unknown>>(PLATFORM_CONFIG.endpoints.banking.accountSnapshot);

}



export async function exchangeOAuthCode(

  code: string,

  state: string,

): Promise<{ sessionToken: string; user: any }> {

  const params = new URLSearchParams({ code, state });

  const result = await apiCall<{ app_session_id: string; user: any }>(

    `/api/oauth/mobile?${params.toString()}`,

  );

  return { sessionToken: result.app_session_id, user: result.user };

}



export async function establishSession(token: string): Promise<boolean> {

  await Auth.setSessionToken(token);

  return true;

}





export interface FintechBeneficiary {

  id: number;

  beneficiaryName: string;

  accountNumber: string;

  bankName: string;

  isFrequent?: boolean;

}



export interface FintechPreferences {

  theme: "light" | "dark" | "auto";

  language: string;

  notificationsEnabled: boolean;

  biometricEnabled: boolean;

  twoFactorEnabled: boolean;

}



export async function fetchTransactionById(id: number): Promise<FintechTransaction> {

  const res = await apiCall<{ transaction: FintechTransaction }>(

    `${PLATFORM_CONFIG.endpoints.banking.transactions}/${id}`,

  );

  return res.transaction;

}



export async function fetchBeneficiaries(): Promise<FintechBeneficiary[]> {

  const res = await apiCall<{ beneficiaries?: FintechBeneficiary[] }>(

    "/api/v1/fintech/beneficiaries",

  );

  return res.beneficiaries ?? [];

}



export async function createBeneficiary(payload: {

  beneficiaryName: string;

  accountNumber: string;

  bankName: string;

}): Promise<FintechBeneficiary> {

  const res = await apiCall<{ beneficiary: FintechBeneficiary }>(

    "/api/v1/fintech/beneficiaries",

    {

      method: "POST",

      body: JSON.stringify(payload),

    },

  );

  return res.beneficiary;

}



export async function deleteBeneficiary(id: number): Promise<void> {

  await apiCall(`/api/v1/fintech/beneficiaries/${id}`, { method: "DELETE" });

}



export async function fetchPreferences(): Promise<FintechPreferences> {

  const res = await apiCall<{ preferences: FintechPreferences }>(

    "/api/v1/fintech/preferences",

  );

  return res.preferences;

}

