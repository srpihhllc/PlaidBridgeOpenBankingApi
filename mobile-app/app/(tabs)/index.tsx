import { Image } from "expo-image";
import { useRouter, Link } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, View, ScrollView, FlatList } from "react-native";

import { HelloWave } from "@/components/hello-wave";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { BalanceCard } from "@/components/balance-card";
import { QuickActionButton } from "@/components/quick-action-button";
import { TransactionItem } from "@/components/transaction-item";
import { BiometricLoginButton } from "@/components/biometric-login-button";
import { getLoginUrl } from "@/constants/oauth";
import { useAuth } from "@/hooks/use-auth";
import { useThemeColor } from "@/hooks/use-theme-color";
import { trpc } from "@/lib/trpc";

export default function HomeScreen() {
  const { user, loading, isAuthenticated, logout } = useAuth();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const router = useRouter();

  const { data: accounts = [] } = trpc.accounts.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const { data: transactions = [] } = trpc.transactions.list.useQuery(
    { limit: 5, offset: 0 },
    { enabled: isAuthenticated }
  );

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");

  useEffect(() => {
    console.log("[HomeScreen] Auth state:", {
      hasUser: !!user,
      loading,
      isAuthenticated,
      user: user ? { id: user.id, openId: user.openId, name: user.name, email: user.email } : null,
    });
  }, [user, loading, isAuthenticated]);

  const handleLogin = async () => {
    try {
      console.log("[Auth] Login button clicked");
      setIsLoggingIn(true);
      const loginUrl = getLoginUrl();
      console.log("[Auth] Generated login URL:", loginUrl);

      if (Platform.OS === "web") {
        console.log("[Auth] Web platform: redirecting to OAuth in same tab...");
        window.location.href = loginUrl;
        return;
      }

      console.log("[Auth] Opening OAuth URL in browser...");
      const result = await WebBrowser.openAuthSessionAsync(
        loginUrl,
        undefined,
        {
          preferEphemeralSession: false,
          showInRecents: true,
        },
      );

      console.log("[Auth] WebBrowser result:", result);
      if (result.type === "cancel") {
        console.log("[Auth] OAuth cancelled by user");
      } else if (result.type === "dismiss") {
        console.log("[Auth] OAuth dismissed");
      } else if (result.type === "success" && result.url) {
        console.log("[Auth] OAuth session successful, navigating to callback:", result.url);
        try {
          let url: URL;
          if (result.url.startsWith("exp://") || result.url.startsWith("exps://")) {
            const urlStr = result.url.replace(/^exp(s)?:\/\//, "http://");
            url = new URL(urlStr);
          } else {
            url = new URL(result.url);
          }

          const code = url.searchParams.get("code");
          const state = url.searchParams.get("state");
          const error = url.searchParams.get("error");

          console.log("[Auth] Extracted params from callback URL:", {
            code: code?.substring(0, 20) + "...",
            state: state?.substring(0, 20) + "...",
            error,
          });

          if (error) {
            console.error("[Auth] OAuth error in callback:", error);
            return;
          }

          if (code && state) {
            console.log("[Auth] Navigating to callback route with params...");
            router.push({
              pathname: "/oauth/callback" as any,
              params: { code, state },
            });
          } else {
            console.error("[Auth] Missing code or state in callback URL");
          }
        } catch (err) {
          console.error("[Auth] Failed to parse callback URL:", err, result.url);
          const codeMatch = result.url.match(/[?&]code=([^&]+)/);
          const stateMatch = result.url.match(/[?&]state=([^&]+)/);

          if (codeMatch && stateMatch) {
            const code = decodeURIComponent(codeMatch[1]);
            const state = decodeURIComponent(stateMatch[1]);
            console.log("[Auth] Fallback: extracted params via regex, navigating...");
            router.push({
              pathname: "/oauth/callback" as any,
              params: { code, state },
            });
          } else {
            console.error("[Auth] Could not extract code/state from URL");
          }
        }
      }
    } catch (error) {
      console.error("[Auth] Login error:", error);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const renderTransactionItem = ({ item }: { item: any }) => (
    <TransactionItem
      id={item.id}
      type={item.transactionType}
      amount={item.amount}
      recipientName={item.recipientName}
      description={item.description}
      status={item.status}
      date={new Date(item.createdAt)}
      onPress={() => router.push(`/transaction-details?id=${item.id}`)}
    />
  );

  const primaryAccount = accounts[0];
  const totalBalance = accounts.reduce((sum, acc) => sum + parseFloat(acc.balance), 0);

  return (
    <ScrollView style={styles.scrollView}>
      <ThemedView style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <ThemedText type="subtitle">Welcome back,</ThemedText>
            <View style={styles.titleContainer}>
              <ThemedText type="title">{user?.name || "User"}</ThemedText>
              <HelloWave />
            </View>
          </View>
        </View>

        {loading ? (
          <ActivityIndicator size="large" />
        ) : isAuthenticated && user ? (
          <>
            {/* Balance Card */}
            {primaryAccount ? (
              <BalanceCard
                accountName={primaryAccount.accountName}
                balance={primaryAccount.balance}
                currency={primaryAccount.currency}
                accountNumber={primaryAccount.accountNumber}
              />
            ) : (
              <ThemedView style={[styles.emptyCard, { backgroundColor: cardBgColor }]}>
                <ThemedText type="subtitle">No accounts yet</ThemedText>
                <ThemedText style={[styles.emptyCardText, { color: textColor, opacity: 0.6 }]}>
                  Create your first account to get started
                </ThemedText>
              </ThemedView>
            )}

            {/* Quick Actions */}
            <View style={styles.quickActionsContainer}>
              <ThemedText type="defaultSemiBold" style={styles.sectionTitle}>
                Quick Actions
              </ThemedText>
              <View style={styles.quickActions}>
                <QuickActionButton
                  icon="📤"
                  label="Send"
                  onPress={() => router.push("/send-money")}
                />
                <QuickActionButton
                  icon="📥"
                  label="Request"
                  onPress={() => console.log("Request pressed")}
                />
                <QuickActionButton
                  icon="💳"
                  label="Pay Bill"
                  onPress={() => console.log("Pay Bill pressed")}
                />
                <QuickActionButton
                  icon="📱"
                  label="Recharge"
                  onPress={() => console.log("Recharge pressed")}
                />
              </View>
            </View>

            {/* Recent Transactions */}
            <View style={styles.transactionsContainer}>
              <View style={styles.transactionsHeader}>
                <ThemedText type="defaultSemiBold" style={styles.sectionTitle}>
                  Recent Transactions
                </ThemedText>
                <Pressable onPress={() => router.push("/accounts")}>
                  <ThemedText style={[styles.viewAll, { color: "#0066FF" }]}>
                    View All
                  </ThemedText>
                </Pressable>
              </View>

              {transactions.length > 0 ? (
                <FlatList
                  data={transactions}
                  keyExtractor={(item) => item.id.toString()}
                  renderItem={renderTransactionItem}
                  scrollEnabled={false}
                />
              ) : (
                <ThemedView style={[styles.emptyTransactions, { backgroundColor: cardBgColor }]}>
                  <ThemedText style={[styles.emptyText, { color: textColor, opacity: 0.6 }]}>
                    No transactions yet
                  </ThemedText>
                </ThemedView>
              )}
            </View>

            {/* Logout Button */}
            <Pressable
              onPress={logout}
              style={({ pressed }) => [
                styles.logoutButton,
                pressed && styles.logoutButtonPressed,
              ]}
            >
              <ThemedText style={styles.logoutText}>Logout</ThemedText>
            </Pressable>
          </>
        ) : (
          <>
            <BiometricLoginButton
              onSuccess={handleLogin}
              onError={(error) => console.error("Biometric login failed:", error)}
            />
            <Pressable
              onPress={handleLogin}
              disabled={isLoggingIn}
              style={[styles.loginButton, isLoggingIn && styles.loginButtonDisabled]}
            >
              {isLoggingIn ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <ThemedText style={styles.loginText}>Login with Email</ThemedText>
              )}
            </Pressable>
          </>
        )}
      </ThemedView>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollView: {
    flex: 1,
  },
  container: {
    flex: 1,
    padding: 16,
  },
  header: {
    marginBottom: 24,
  },
  titleContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  emptyCard: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 160,
  },
  emptyCardText: {
    fontSize: 14,
    marginTop: 8,
  },
  quickActionsContainer: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    marginBottom: 12,
  },
  quickActions: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  transactionsContainer: {
    marginBottom: 24,
  },
  transactionsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  viewAll: {
    fontSize: 14,
    fontWeight: "600",
  },
  emptyTransactions: {
    borderRadius: 12,
    padding: 20,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 100,
  },
  emptyText: {
    fontSize: 14,
  },
  loginButton: {
    backgroundColor: "#0066FF",
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 50,
    marginTop: 20,
  },
  loginButtonDisabled: {
    opacity: 0.6,
  },
  loginText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  logoutButton: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    backgroundColor: "rgba(255, 59, 48, 0.1)",
    alignItems: "center",
    marginTop: 20,
  },
  logoutButtonPressed: {
    opacity: 0.7,
  },
  logoutText: {
    color: "#FF3B30",
    fontSize: 14,
    fontWeight: "500",
  },
});
