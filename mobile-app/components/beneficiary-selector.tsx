import {
  StyleSheet,
  View,
  FlatList,
  Pressable,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { useState, useMemo } from "react";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { trpc } from "@/lib/trpc";

export interface BeneficiaryOption {
  id: number;
  beneficiaryName: string;
  accountNumber: string;
  bankName: string;
}

interface BeneficiarySelectorProps {
  onSelectBeneficiary: (beneficiary: BeneficiaryOption) => void;
  selectedId?: number;
}

export function BeneficiarySelector({
  onSelectBeneficiary,
  selectedId,
}: BeneficiarySelectorProps) {
  const textColor = useThemeColor({}, "text");
  const tintColor = useThemeColor({}, "tint");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch beneficiaries
  const { data: beneficiaries = [], isLoading } = trpc.beneficiaries.list.useQuery();

  // Filter beneficiaries based on search query
  const filteredBeneficiaries = useMemo(() => {
    if (!searchQuery.trim()) {
      return beneficiaries;
    }

    const query = searchQuery.toLowerCase();
    return beneficiaries.filter(
      (b) =>
        b.beneficiaryName.toLowerCase().includes(query) ||
        b.bankName.toLowerCase().includes(query) ||
        b.accountNumber.includes(query)
    );
  }, [beneficiaries, searchQuery]);

  const BeneficiaryItem = ({ item }: { item: BeneficiaryOption }) => (
    <Pressable
      onPress={() => {
        onSelectBeneficiary(item);
        setSearchQuery("");
      }}
      style={({ pressed }) => [
        styles.beneficiaryItem,
        selectedId === item.id && styles.beneficiaryItemSelected,
        pressed && styles.beneficiaryItemPressed,
      ]}
    >
      <View style={styles.beneficiaryContent}>
        <ThemedText type="defaultSemiBold" style={styles.beneficiaryName}>
          {item.beneficiaryName}
        </ThemedText>
        <ThemedText style={[styles.bankName, { color: textColor, opacity: 0.6 }]}>
          {item.bankName}
        </ThemedText>
        <ThemedText style={[styles.accountNumber, { color: textColor, opacity: 0.5 }]}>
          •••• {item.accountNumber.slice(-4)}
        </ThemedText>
      </View>
      {selectedId === item.id && (
        <View style={[styles.checkmark, { backgroundColor: tintColor }]}>
          <ThemedText style={styles.checkmarkText}>✓</ThemedText>
        </View>
      )}
    </Pressable>
  );

  return (
    <ThemedView style={styles.container}>
      {/* Search Input */}
      <View style={styles.searchContainer}>
        <TextInput
          style={[styles.searchInput, { color: textColor }]}
          placeholder="Search beneficiaries..."
          placeholderTextColor={textColor}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery && (
          <Pressable onPress={() => setSearchQuery("")} style={styles.clearButton}>
            <ThemedText style={styles.clearButtonText}>✕</ThemedText>
          </Pressable>
        )}
      </View>

      {/* Beneficiaries List */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator color={tintColor} />
        </View>
      ) : filteredBeneficiaries.length === 0 ? (
        <View style={styles.emptyContainer}>
          <ThemedText style={[styles.emptyText, { color: textColor, opacity: 0.6 }]}>
            {searchQuery ? "No beneficiaries found" : "No saved beneficiaries"}
          </ThemedText>
        </View>
      ) : (
        <FlatList
          data={filteredBeneficiaries}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => <BeneficiaryItem item={item} />}
          scrollEnabled={false}
          contentContainerStyle={styles.listContent}
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
    borderRadius: 12,
    overflow: "hidden",
  },
  searchContainer: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0, 0, 0, 0.1)",
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  clearButton: {
    padding: 4,
  },
  clearButtonText: {
    fontSize: 16,
    color: "#999",
  },
  loadingContainer: {
    paddingVertical: 20,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyContainer: {
    paddingVertical: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyText: {
    fontSize: 13,
  },
  listContent: {
    paddingHorizontal: 0,
  },
  beneficiaryItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0, 0, 0, 0.05)",
  },
  beneficiaryItemSelected: {
    backgroundColor: "rgba(0, 102, 255, 0.05)",
  },
  beneficiaryItemPressed: {
    opacity: 0.7,
  },
  beneficiaryContent: {
    flex: 1,
    gap: 4,
  },
  beneficiaryName: {
    fontSize: 14,
  },
  bankName: {
    fontSize: 12,
  },
  accountNumber: {
    fontSize: 11,
  },
  checkmark: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: 8,
  },
  checkmarkText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "bold",
  },
});
