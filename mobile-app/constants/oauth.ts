import * as Linking from "expo-linking";

import * as ReactNative from "react-native";



export const PLATFORM_CONFIG = {

  appName: "PlaidBridge Shield",

  company: "Sir Pollards Internal Holistic Healing LLC",

  apiBaseUrl: (

    process.env.EXPO_PUBLIC_API_BASE_URL ?? "https://srpihhllc.pythonanywhere.com"

  ).replace(/\/$/, ""),

  deepLinkScheme: "plaidbridge",

  endpoints: {

    auth: {

      login: "/auth/api/token",

      refresh: "/auth/api/refresh",

      me: "/auth/api/me",

      logout: "/auth/api/logout",

    },

    plaid: {

      createLinkToken: "/create_link_token",

      exchangePublicToken: "/exchange_public_token",

      transactions: "/transactions",

    },

    banking: {

      accounts: "/api/v1/fintech/accounts",

      cards: "/api/v1/fintech/cards",

      transactions: "/api/v1/fintech/transactions",

      transfers: "/api/v1/fintech/transfers",

      accountSnapshot: "/api/v1/fintech/sandbox/account_snapshot",

    },

    shield: {

      verifyLenderKyc: "/api/v1/fintech/shield/kyc/verify",

      scopedProxySnapshot: "/api/v1/fintech/shield/proxy/snapshot",

      auditAgreement: "/api/v1/fintech/shield/agreement/audit",

      signDisclosure: "/api/v1/fintech/shield/disclosure/sign",

      disburseEscrow: "/api/v1/fintech/shield/escrow/disburse",

      approveManualLink: "/api/v1/fintech/link/manual/approve",

    },

  },

} as const;



export const API_BASE_URL = PLATFORM_CONFIG.apiBaseUrl;

export const OAUTH_PORTAL_URL = PLATFORM_CONFIG.apiBaseUrl;

export const OAUTH_SERVER_URL = PLATFORM_CONFIG.apiBaseUrl;

export const APP_ID = process.env.EXPO_PUBLIC_APP_ID ?? "plaidbridge-shield";

export const OWNER_OPEN_ID = "";

export const OWNER_NAME = "Terence Pollard Sr";



export const SESSION_TOKEN_KEY = "pb_shield_access_token";

export const USER_INFO_KEY = "pb_shield_user_profile";



export function getApiBaseUrl(): string {

  return PLATFORM_CONFIG.apiBaseUrl;

}



export const getLoginUrl = () => {

  if (ReactNative.Platform.OS === "web") {

    return `${getApiBaseUrl()}/auth/login`;

  }

  return Linking.createURL("/oauth/callback", {

    scheme: PLATFORM_CONFIG.deepLinkScheme,

  });

};

