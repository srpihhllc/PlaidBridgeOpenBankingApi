import React from "react";
import { View, StyleSheet } from "react-native";
import { Stack } from "expo-router";
import PlaidLinkButton from "@/components/PlaidLinkButton";

/**
 * Simple demo screen for Plaid Link
 * Visit /plaid/link in your Expo Router (route path depends on your router setup)
 */

export default function PlaidLinkScreen() {
  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: "Link Bank" }} />
      <PlaidLinkButton />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
});
