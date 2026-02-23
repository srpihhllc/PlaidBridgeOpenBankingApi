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
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { trpc } from "@/lib/trpc";

export default function BeneficiariesScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const textColor = useThemeColor({}, "text");
  const tintColor = useThemeColor({}, "tint");

  const [refreshing, setRefreshing] = useState(false);

  // Fetch beneficiaries
  const { data: beneficiaries = [], isLoading, refetch } = trpc.beneficiaries.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  // Delete beneficiary mutation
  const deleteMutation = trpc.beneficiaries.delete.useMutation({
    onSuccess: () => {
      refetch();
    },
  });

  const handleRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleAddBeneficiary = () => {
    router.push("/add-beneficiary");
  };

  const handleEditBeneficiary = (beneficiaryId: number) => {
    router.push({
      pathname: "/add-beneficiary",
      params: { id: beneficiaryId },
    });
  };

  const handleDeleteBeneficiary = (beneficiaryId: number) => {
    deleteMutation.mutate({ id: beneficiaryId });
  };

  const BeneficiaryCard = ({
    id,
    beneficiaryName,
    accountNumber,
    bankName,
  }: {
    id: number;
    beneficiaryName: string;
    accountNumber: string;
    bankName: string;
  }) => (
    <ThemedView style={styles.card}>
      <View style={styles.cardContent}>
        <View style={styles.cardHeader}>
          <ThemedText type="defaultSemiBold" style={styles.beneficiaryName}>
            {beneficiaryName}
          </ThemedText>
        </View>

        <ThemedText style={[styles.bankName, { color: textColor, opacity: 0.7 }]}>
          {bankName}
        </ThemedText>

        <View style={styles.accountNumberContainer}>
          <ThemedText style={[styles.accountLabel, { color: textColor, opacity: 0.5 }]}>
            Account
          </ThemedText>
          <ThemedText style={[styles.accountNumber, { color: textColor, opacity: 0.8 }]}>
            •••• {accountNumber.slice(-4)}
          </ThemedText>
        </View>
      </View>

      <View style={styles.actions}>
        <Pressable
          onPress={() => handleEditBeneficiary(id)}
          style={({ pressed }) => [styles.actionButton, pressed && styles.actionButtonPressed]}
        >
          <ThemedText style={styles.editIcon}>✏️</ThemedText>
        </Pressable>

        <Pressable
          onPress={() => handleDeleteBeneficiary(id)}
          style={({ pressed }) => [
            styles.actionButton,
            styles.deleteButton,
            pressed && styles.actionButtonPressed,
          ]}
        >
          <ThemedText style={styles.deleteIcon}>🗑️</ThemedText>
        </Pressable>
      </View>
    </ThemedView>
  );

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
        <ThemedText type="title">Beneficiaries</ThemedText>
        <Pressable
          onPress={handleAddBeneficiary}
          style={({ pressed }) => [styles.addButton, pressed && styles.addButtonPressed]}
        >
          <ThemedText style={styles.addButtonText}>+ Add</ThemedText>
        </Pressable>
      </View>

      {/* Content */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={tintColor} />
        </View>
      ) : beneficiaries.length === 0 ? (
        <View style={styles.emptyContainer}>
          <ThemedText style={styles.emptyIcon}>👥</ThemedText>
          <ThemedText type="subtitle" style={styles.emptyTitle}>
            No beneficiaries yet
          </ThemedText>
          <ThemedText style={[styles.emptyText, { color: textColor, opacity: 0.6 }]}>
            Add a beneficiary to quickly send money to frequent recipients
          </ThemedText>
          <Pressable
            onPress={handleAddBeneficiary}
            style={({ pressed }) => [styles.emptyAddButton, pressed && styles.emptyAddButtonPressed]}
          >
            <ThemedText style={styles.emptyAddButtonText}>Add Beneficiary</ThemedText>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={beneficiaries}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <BeneficiaryCard
              id={item.id}
              beneficiaryName={item.beneficiaryName}
              accountNumber={item.accountNumber}
              bankName={item.bankName}
            />
          )}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 16,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },
  addButton: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: "#0066FF",
  },
  addButtonPressed: {
    opacity: 0.7,
  },
  addButtonText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
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
    marginBottom: 24,
  },
  emptyAddButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    backgroundColor: "#0066FF",
  },
  emptyAddButtonPressed: {
    opacity: 0.7,
  },
  emptyAddButtonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  listContent: {
    paddingBottom: 20,
  },
  card: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    marginBottom: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
  cardContent: {
    flex: 1,
    gap: 8,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  beneficiaryName: {
    fontSize: 16,
  },
  accountType: {
    fontSize: 12,
  },
  bankName: {
    fontSize: 13,
  },
  accountNumberContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  accountLabel: {
    fontSize: 11,
  },
  accountNumber: {
    fontSize: 12,
    fontWeight: "500",
  },
  actions: {
    flexDirection: "row",
    gap: 8,
  },
  actionButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: "rgba(0, 102, 255, 0.1)",
    justifyContent: "center",
    alignItems: "center",
  },
  deleteButton: {
    backgroundColor: "rgba(255, 59, 48, 0.1)",
  },
  actionButtonPressed: {
    opacity: 0.7,
  },
  editIcon: {
    fontSize: 16,
  },
  deleteIcon: {
    fontSize: 16,
  },
});
