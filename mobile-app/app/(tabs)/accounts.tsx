import { FlatList, StyleSheet, View, Pressable, ActivityIndicator } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { trpc } from "@/lib/trpc";
import { useState } from "react";

export default function AccountsScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);

  const { data: accounts = [], isLoading, error } = trpc.accounts.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");

  if (authLoading || isLoading) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ActivityIndicator size="large" color={tintColor} />
      </ThemedView>
    );
  }

  if (!isAuthenticated) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText type="title">Please log in</ThemedText>
      </ThemedView>
    );
  }

  if (error) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText type="subtitle">Error loading accounts</ThemedText>
      </ThemedView>
    );
  }

  const renderAccountItem = ({ item }: { item: any }) => (
    <Pressable
      onPress={() => setSelectedAccountId(item.id)}
      style={({ pressed }) => [
        styles.accountCard,
        { backgroundColor: cardBgColor },
        pressed && styles.accountCardPressed,
      ]}
    >
      <View style={styles.accountHeader}>
        <View>
          <ThemedText type="defaultSemiBold" style={styles.accountName}>
            {item.accountName}
          </ThemedText>
          <ThemedText style={[styles.accountType, { color: textColor, opacity: 0.6 }]}>
            {item.accountType.charAt(0).toUpperCase() + item.accountType.slice(1)} • ••••{item.accountNumber.slice(-4)}
          </ThemedText>
        </View>
        <View style={styles.statusBadge}>
          <ThemedText style={[styles.statusText, { color: item.status === "active" ? "#34C759" : "#FF3B30" }]}>
            {item.status.toUpperCase()}
          </ThemedText>
        </View>
      </View>

      <View style={styles.balanceSection}>
        <ThemedText style={[styles.balanceLabel, { color: textColor, opacity: 0.6 }]}>
          Available Balance
        </ThemedText>
        <ThemedText type="title" style={styles.balanceAmount}>
          {item.currency} {parseFloat(item.balance).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </ThemedText>
      </View>
    </Pressable>
  );

  return (
    <ThemedView
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          paddingBottom: Math.max(insets.bottom, 20),
          paddingLeft: Math.max(insets.left, 20),
          paddingRight: Math.max(insets.right, 20),
        },
      ]}
    >
      <ThemedText type="title" style={styles.title}>
        My Accounts
      </ThemedText>

      {accounts.length === 0 ? (
        <View style={styles.emptyState}>
          <ThemedText type="subtitle">No accounts yet</ThemedText>
          <ThemedText style={[styles.emptyStateText, { color: textColor, opacity: 0.6 }]}>
            Create your first account to get started
          </ThemedText>
        </View>
      ) : (
        <FlatList
          data={accounts}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderAccountItem}
          scrollEnabled={false}
          contentContainerStyle={styles.listContent}
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  title: {
    marginBottom: 20,
  },
  listContent: {
    gap: 12,
  },
  accountCard: {
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  accountCardPressed: {
    opacity: 0.7,
  },
  accountHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  accountName: {
    fontSize: 16,
    marginBottom: 4,
  },
  accountType: {
    fontSize: 12,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: "rgba(0, 0, 0, 0.05)",
  },
  statusText: {
    fontSize: 10,
    fontWeight: "600",
  },
  balanceSection: {
    gap: 4,
  },
  balanceLabel: {
    fontSize: 12,
  },
  balanceAmount: {
    fontSize: 24,
    fontWeight: "700",
  },
  emptyState: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
  },
  emptyStateText: {
    fontSize: 14,
    textAlign: "center",
  },
});
