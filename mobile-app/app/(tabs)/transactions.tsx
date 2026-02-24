import {
  StyleSheet,
  View,
  FlatList,
  Pressable,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useState } from "react";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { SearchBar } from "@/components/search-bar";
import { TransactionFiltersModal } from "@/components/transaction-filters-modal";
import { TransactionItem } from "@/components/transaction-item";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { useTransactionFilter } from "@/hooks/use-transaction-filter";
import { trpc } from "@/lib/trpc";

export default function TransactionsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const textColor = useThemeColor({}, "text");
  const tintColor = useThemeColor({}, "tint");

  const [showFiltersModal, setShowFiltersModal] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Fetch transactions
  const { data: transactions = [], isLoading, refetch } = trpc.transactions.list.useQuery(
    { limit: 100, offset: 0 },
    { enabled: isAuthenticated }
  );

  // Use filter hook
  const {
    filters,
    filteredTransactions,
    updateSearchQuery,
    updateTransactionType,
    updateDateRange,
    updateAmountRange,
    clearFilters,
    hasActiveFilters,
  } = useTransactionFilter(transactions);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleApplyFilters = (newFilters: {
    transactionType: string | null;
    startDate: Date | null;
    endDate: Date | null;
    minAmount: number | null;
    maxAmount: number | null;
  }) => {
    updateTransactionType(newFilters.transactionType);
    updateDateRange(newFilters.startDate, newFilters.endDate);
    updateAmountRange(newFilters.minAmount, newFilters.maxAmount);
  };

  const handleClearSearch = () => {
    updateSearchQuery("");
  };

  const handleTransactionPress = (transactionId: number) => {
    router.push({
      pathname: "/transaction-details",
      params: { id: transactionId },
    });
  };

  return (
    <ThemedView
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          paddingBottom: Math.max(insets.bottom, 20),
        },
      ]}
    >
      {/* Header */}
      <View style={styles.header}>
        <ThemedText type="title">Transactions</ThemedText>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <SearchBar
          value={filters.searchQuery}
          onChangeText={updateSearchQuery}
          onClear={handleClearSearch}
          placeholder="Search by name, date, or amount..."
        />
      </View>

      {/* Filter Button */}
      <View style={styles.filterButtonContainer}>
        <Pressable
          onPress={() => setShowFiltersModal(true)}
          style={({ pressed }) => [
            styles.filterButton,
            hasActiveFilters() && styles.filterButtonActive,
            pressed && styles.filterButtonPressed,
          ]}
        >
          <ThemedText style={styles.filterButtonText}>
            {hasActiveFilters() ? "🔍 Filters Active" : "⚙️ Filters"}
          </ThemedText>
        </Pressable>

        {hasActiveFilters() && (
          <Pressable
            onPress={clearFilters}
            style={({ pressed }) => [styles.clearButton, pressed && styles.clearButtonPressed]}
          >
            <ThemedText style={styles.clearButtonText}>Clear</ThemedText>
          </Pressable>
        )}
      </View>

      {/* Transactions List */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={tintColor} />
        </View>
      ) : filteredTransactions.length === 0 ? (
        <View style={styles.emptyContainer}>
          <ThemedText style={styles.emptyIcon}>📭</ThemedText>
          <ThemedText type="subtitle" style={styles.emptyTitle}>
            No transactions found
          </ThemedText>
          <ThemedText style={[styles.emptyText, { color: textColor, opacity: 0.6 }]}>
            {filters.searchQuery || hasActiveFilters()
              ? "Try adjusting your search or filters"
              : "Your transaction history will appear here"}
          </ThemedText>
        </View>
      ) : (
        <FlatList
          data={filteredTransactions}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <TransactionItem
              id={item.id}
              type={item.transactionType as "transfer" | "deposit" | "withdrawal" | "payment" | "recharge"}
              amount={item.amount}
              recipientName={item.recipientName || undefined}
              description={item.description || undefined}
              status={item.status as "pending" | "completed" | "failed" | "cancelled"}
              date={new Date(item.createdAt)}
              onPress={() => handleTransactionPress(item.id)}
            />
          )}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* Filters Modal */}
      <TransactionFiltersModal
        visible={showFiltersModal}
        onClose={() => setShowFiltersModal(false)}
        onApply={handleApplyFilters}
        onClear={clearFilters}
        currentFilters={{
          transactionType: filters.transactionType,
          startDate: filters.startDate,
          endDate: filters.endDate,
          minAmount: filters.minAmount,
          maxAmount: filters.maxAmount,
        }}
      />
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 16,
  },
  header: {
    marginBottom: 20,
  },
  searchContainer: {
    marginBottom: 12,
  },
  filterButtonContainer: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 16,
  },
  filterButton: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
    alignItems: "center",
  },
  filterButtonActive: {
    borderColor: "#0066FF",
    backgroundColor: "rgba(0, 102, 255, 0.05)",
  },
  filterButtonPressed: {
    opacity: 0.7,
  },
  filterButtonText: {
    fontSize: 13,
    fontWeight: "500",
  },
  clearButton: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(255, 59, 48, 0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  clearButtonPressed: {
    opacity: 0.7,
  },
  clearButtonText: {
    fontSize: 12,
    fontWeight: "500",
    color: "#FF3B30",
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyTitle: {
    marginBottom: 8,
    textAlign: "center",
  },
  emptyText: {
    fontSize: 14,
    lineHeight: 20,
    textAlign: "center",
  },
  listContent: {
    paddingBottom: 20,
  },
  transactionPressed: {
    opacity: 0.7,
  },
});
