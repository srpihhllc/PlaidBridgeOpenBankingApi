import { StyleSheet, View, Pressable, Modal, ScrollView, TextInput } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ThemedText } from "./themed-text";
import { ThemedView } from "./themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useState } from "react";

interface TransactionFiltersModalProps {
  visible: boolean;
  onClose: () => void;
  onApply: (filters: {
    transactionType: string | null;
    startDate: Date | null;
    endDate: Date | null;
    minAmount: number | null;
    maxAmount: number | null;
  }) => void;
  onClear: () => void;
  currentFilters: {
    transactionType: string | null;
    startDate: Date | null;
    endDate: Date | null;
    minAmount: number | null;
    maxAmount: number | null;
  };
}

const TRANSACTION_TYPES = [
  { label: "All Types", value: "all" },
  { label: "Transfer", value: "transfer" },
  { label: "Deposit", value: "deposit" },
  { label: "Withdrawal", value: "withdrawal" },
  { label: "Payment", value: "payment" },
  { label: "Recharge", value: "recharge" },
];

export function TransactionFiltersModal({
  visible,
  onClose,
  onApply,
  onClear,
  currentFilters,
}: TransactionFiltersModalProps) {
  const insets = useSafeAreaInsets();
  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");
  const errorColor = useThemeColor({}, "error");

  const [selectedType, setSelectedType] = useState(currentFilters.transactionType || "all");
  const [startDate, setStartDate] = useState(
    currentFilters.startDate ? currentFilters.startDate.toISOString().split("T")[0] : ""
  );
  const [endDate, setEndDate] = useState(
    currentFilters.endDate ? currentFilters.endDate.toISOString().split("T")[0] : ""
  );
  const [minAmount, setMinAmount] = useState(
    currentFilters.minAmount ? currentFilters.minAmount.toString() : ""
  );
  const [maxAmount, setMaxAmount] = useState(
    currentFilters.maxAmount ? currentFilters.maxAmount.toString() : ""
  );

  const handleApply = () => {
    onApply({
      transactionType: selectedType === "all" ? null : selectedType,
      startDate: startDate ? new Date(startDate) : null,
      endDate: endDate ? new Date(endDate) : null,
      minAmount: minAmount ? parseFloat(minAmount) : null,
      maxAmount: maxAmount ? parseFloat(maxAmount) : null,
    });
    onClose();
  };

  const handleClear = () => {
    setSelectedType("all");
    setStartDate("");
    setEndDate("");
    setMinAmount("");
    setMaxAmount("");
    onClear();
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={[styles.overlay, { paddingTop: insets.top }]}>
        <ThemedView style={[styles.container, { backgroundColor: cardBgColor }]}>
          {/* Header */}
          <View style={styles.header}>
            <ThemedText type="title">Filters</ThemedText>
            <Pressable onPress={onClose}>
              <ThemedText style={styles.closeButton}>✕</ThemedText>
            </Pressable>
          </View>

          <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
            {/* Transaction Type Filter */}
            <View style={styles.filterSection}>
              <ThemedText type="defaultSemiBold" style={styles.filterTitle}>
                Transaction Type
              </ThemedText>
              <View style={styles.typeOptions}>
                {TRANSACTION_TYPES.map((type) => (
                  <Pressable
                    key={type.value}
                    onPress={() => setSelectedType(type.value)}
                    style={[
                      styles.typeOption,
                      selectedType === type.value && styles.typeOptionSelected,
                    ]}
                  >
                    <ThemedText
                      style={[
                        styles.typeOptionText,
                        selectedType === type.value && { color: tintColor, fontWeight: "600" },
                      ]}
                    >
                      {type.label}
                    </ThemedText>
                  </Pressable>
                ))}
              </View>
            </View>

            {/* Date Range Filter */}
            <View style={styles.filterSection}>
              <ThemedText type="defaultSemiBold" style={styles.filterTitle}>
                Date Range
              </ThemedText>
              <View style={styles.dateInputs}>
                <View style={styles.dateInput}>
                  <ThemedText style={styles.dateLabel}>From</ThemedText>
                  <TextInput
                    style={[styles.input, { color: textColor }]}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={textColor}
                    value={startDate}
                    onChangeText={setStartDate}
                  />
                </View>
                <View style={styles.dateInput}>
                  <ThemedText style={styles.dateLabel}>To</ThemedText>
                  <TextInput
                    style={[styles.input, { color: textColor }]}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={textColor}
                    value={endDate}
                    onChangeText={setEndDate}
                  />
                </View>
              </View>
            </View>

            {/* Amount Range Filter */}
            <View style={styles.filterSection}>
              <ThemedText type="defaultSemiBold" style={styles.filterTitle}>
                Amount Range
              </ThemedText>
              <View style={styles.amountInputs}>
                <View style={styles.amountInput}>
                  <ThemedText style={styles.amountLabel}>Min</ThemedText>
                  <TextInput
                    style={[styles.input, { color: textColor }]}
                    placeholder="0.00"
                    placeholderTextColor={textColor}
                    keyboardType="decimal-pad"
                    value={minAmount}
                    onChangeText={setMinAmount}
                  />
                </View>
                <View style={styles.amountInput}>
                  <ThemedText style={styles.amountLabel}>Max</ThemedText>
                  <TextInput
                    style={[styles.input, { color: textColor }]}
                    placeholder="0.00"
                    placeholderTextColor={textColor}
                    keyboardType="decimal-pad"
                    value={maxAmount}
                    onChangeText={setMaxAmount}
                  />
                </View>
              </View>
            </View>
          </ScrollView>

          {/* Action Buttons */}
          <View style={styles.footer}>
            <Pressable
              onPress={handleClear}
              style={({ pressed }) => [
                styles.clearButton,
                pressed && styles.buttonPressed,
              ]}
            >
              <ThemedText style={[styles.clearButtonText, { color: errorColor }]}>
                Clear Filters
              </ThemedText>
            </Pressable>

            <Pressable
              onPress={handleApply}
              style={({ pressed }) => [
                styles.applyButton,
                { backgroundColor: tintColor },
                pressed && styles.buttonPressed,
              ]}
            >
              <ThemedText style={styles.applyButtonText}>Apply Filters</ThemedText>
            </Pressable>
          </View>
        </ThemedView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  container: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "90%",
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0, 0, 0, 0.1)",
  },
  closeButton: {
    fontSize: 24,
    opacity: 0.6,
  },
  content: {
    paddingVertical: 16,
  },
  filterSection: {
    marginBottom: 24,
  },
  filterTitle: {
    fontSize: 14,
    marginBottom: 12,
  },
  typeOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  typeOption: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
  typeOptionSelected: {
    borderColor: "#0066FF",
    backgroundColor: "rgba(0, 102, 255, 0.05)",
  },
  typeOptionText: {
    fontSize: 12,
  },
  dateInputs: {
    flexDirection: "row",
    gap: 12,
  },
  dateInput: {
    flex: 1,
  },
  dateLabel: {
    fontSize: 12,
    marginBottom: 6,
    opacity: 0.6,
  },
  amountInputs: {
    flexDirection: "row",
    gap: 12,
  },
  amountInput: {
    flex: 1,
  },
  amountLabel: {
    fontSize: 12,
    marginBottom: 6,
    opacity: 0.6,
  },
  input: {
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  footer: {
    flexDirection: "row",
    gap: 12,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: "rgba(0, 0, 0, 0.1)",
  },
  clearButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 59, 48, 0.3)",
  },
  applyButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  applyButtonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  clearButtonText: {
    fontSize: 14,
    fontWeight: "600",
  },
  buttonPressed: {
    opacity: 0.7,
  },
});
