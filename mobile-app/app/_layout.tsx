import { DarkTheme, DefaultTheme, ThemeProvider } from "@react-navigation/native";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Stack } from "expo-router";

import { StatusBar } from "expo-status-bar";

import { useState } from "react";

import { GestureHandlerRootView } from "react-native-gesture-handler";

import "react-native-reanimated";

import { SafeAreaProvider, initialWindowMetrics } from "react-native-safe-area-context";



import { useColorScheme } from "@/hooks/use-color-scheme";



export const unstable_settings = {

  anchor: "(tabs)",

};



export default function RootLayout() {

  const colorScheme = useColorScheme();

  const [queryClient] = useState(

    () =>

      new QueryClient({

        defaultOptions: {

          queries: {

            refetchOnWindowFocus: false,

            retry: 1,

          },

        },

      }),

  );



  return (

    <SafeAreaProvider initialMetrics={initialWindowMetrics}>

      <GestureHandlerRootView style={{ flex: 1 }}>

        <QueryClientProvider client={queryClient}>

          <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>

            <Stack>

              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />

              <Stack.Screen name="modal" options={{ presentation: "modal", title: "Modal" }} />

              <Stack.Screen name="oauth/callback" options={{ headerShown: false }} />

            </Stack>

            <StatusBar style="auto" />

          </ThemeProvider>

        </QueryClientProvider>

      </GestureHandlerRootView>

    </SafeAreaProvider>

  );

}

