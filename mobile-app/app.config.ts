import type { ExpoConfig } from "expo/config";



const config: ExpoConfig = {

  name: "PlaidBridge Shield",

  slug: "plaidbridge-shield",

  version: "1.0.0",

  orientation: "portrait",

  icon: "./assets/images/icon.png",

  scheme: "plaidbridge",

  userInterfaceStyle: "automatic",

  newArchEnabled: true,

  ios: {

    supportsTablet: false,

    bundleIdentifier: "com.srpihhllc.plaidbridge",

    infoPlist: {

      NSFaceIDUsageDescription:

        "Authenticate with Face ID to authorize transfers, Plaid connections, and Mock Shield loan disclosures.",

      ITSAppUsesNonExemptEncryption: false,

    },

  },

  android: {

    package: "com.srpihhllc.plaidbridge",

    adaptiveIcon: {

      backgroundColor: "#0B1120",

      foregroundImage: "./assets/images/android-icon-foreground.png",

      backgroundImage: "./assets/images/android-icon-background.png",

      monochromeImage: "./assets/images/android-icon-monochrome.png",

    },

    permissions: ["USE_BIOMETRIC", "USE_FINGERPRINT", "INTERNET"],

  },

  web: {

    bundler: "metro",

    output: "static",

    favicon: "./assets/images/favicon.png",

  },

  plugins: [

    "expo-router",

    "expo-secure-store",

    [

      "expo-local-authentication",

      {

        faceIDPermission:

          "Allow PlaidBridge Shield to use Face ID to protect your escrow wallet and loan disclosures.",

      },

    ],

    [

      "expo-splash-screen",

      {

        image: "./assets/images/splash-icon.png",

        imageWidth: 200,

        resizeMode: "contain",

        backgroundColor: "#0B1120",

      },

    ],

  ],

  experiments: {

    typedRoutes: true,

  },

  extra: {

    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "https://srpihhllc.pythonanywhere.com",

    environment: process.env.EXPO_PUBLIC_ENV ?? "production",

  },

};



export default config;

