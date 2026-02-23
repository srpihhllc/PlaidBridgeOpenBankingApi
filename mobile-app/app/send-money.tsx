import { StyleSheet, View, Pressable, ScrollView, TextInput, ActivityIndicator } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { BiometricConfirmation } from "@/components/biometric-confirmation";
import { BeneficiarySelector, type BeneficiaryOption } from "@/components/beneficiary-selector";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { trpc } from "@/lib/trpc";

export default function SendMoneyScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [recipientName, setRecipientName] = useState("");
  const [recipientAccount, setRecipientAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [step, setStep] = useState<"form" | "review">("form");
  const [showBeneficiarySelector, setShowBeneficiarySelector] = useState(false);

  const { data: accounts = [] } = trpc.accounts.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(
    accounts.length > 0 ? accounts[0].id : null
  );
  const [showBiometricConfirm, setShowBiometricConfirm] = useState(false);

  const createTransactionMutation = trpc.transactions.create.useMutation({
    onSuccess: () => {
      router.back();
    },
  });

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");
  const errorColor = useThemeColor({}, "error");

  const handleReviewClick = () => {
    if (!recipientName || !recipientAccount || !amount || !selectedAccountId) {
      alert("Please fill in all required fields");
      return;
    }
    setStep("review");
  };

  const handleBiometricConfirm = async () => {
    try {
      await createTransactionMutation.mutateAsync({
        accountId: selectedAccountId!,
        transactionType: "transfer",
        amount,
        recipientName,
        recipientAccount,
        description,
      });
      setShowBiometricConfirm(false);
    } catch (error) {
      console.error("Failed to create transaction:", error);
      alert("Failed to send money. Please try again.");
      setShowBiometricConfirm(false);
    }
  };

  const selectedAccount = accounts.find((acc) => acc.id === selectedAccountId);

  if (step === "form") {
    return (
      <ScrollView
        style={[
          styles.container,
          {
            paddingTop: Math.max(insets.top, 20),
            paddingBottom: Math.max(insets.bottom, 20),
          },
        ]}
        contentContainerStyle={{ paddingHorizontal: Math.max(insets.left, 20) }}
      >
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()}>
            <ThemedText style={styles.backButton}>← Back</ThemedText>
          </Pressable>
          <ThemedText type="title">Send Money</ThemedText>
        </View>

        {/* From Account */}
        <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
          <ThemedText type="subtitle" style={styles.sectionTitle}>
            From Account
          </ThemedText>

          <View style={styles.accountSelector}>
            {accounts.map((account) => (
              <Pressable
                key={account.id}
                onPress={() => setSelectedAccountId(account.id)}
                style={[
                  styles.accountOption,
                  selectedAccountId === account.id && styles.accountOptionSelected,
                ]}
              >
                <View>
                  <ThemedText type="defaultSemiBold" style={styles.accountName}>
                    {account.accountName}
                  </ThemedText>
                  <ThemedText style={[styles.accountBalance, { color: textColor, opacity: 0.6 }]}>
                    Balance: {account.currency} {parseFloat(account.balance).toFixed(2)}
                  </ThemedText>
                </View>
              </Pressable>
            ))}
          </View>
        </ThemedView>

        {/* Quick Select Beneficiary */}
        {!showBeneficiarySelector && (
          <Pressable
            onPress={() => setShowBeneficiarySelector(true)}
            style={({ pressed }) => [
              styles.quickSelectButton,
              { borderColor: tintColor },
              pressed && styles.quickSelectButtonPressed,
            ]}
          >
            <ThemedText style={[styles.quickSelectText, { color: tintColor }]}>
              👥 Select from saved beneficiaries
            </ThemedText>
          </Pressable>
        )}

        {/* Beneficiary Selector */}
        {showBeneficiarySelector && (
          <View style={styles.selectorContainer}>
            <View style={styles.selectorHeader}>
              <ThemedText type="subtitle">Select Beneficiary</ThemedText>
              <Pressable
                onPress={() => setShowBeneficiarySelector(false)}
                style={styles.closeSelectorButton}
              >
                <ThemedText style={styles.closeSelectorText}>✕</ThemedText>
              </Pressable>
            </View>
            <BeneficiarySelector
              onSelectBeneficiary={(beneficiary: BeneficiaryOption) => {
                setRecipientName(beneficiary.beneficiaryName);
                setRecipientAccount(beneficiary.accountNumber);
                setShowBeneficiarySelector(false);
              }}
            />
          </View>
        )}

        {/* Recipient Details */}
        <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
          <ThemedText type="subtitle" style={styles.sectionTitle}>
            Recipient Details
          </ThemedText>

          <View style={styles.formGroup}>
            <ThemedText style={[styles.label, { color: textColor }]}>
              Recipient Name *
            </ThemedText>
            <TextInput
              style={[styles.input, { color: textColor }]}
              placeholder="Enter recipient name"
              placeholderTextColor={textColor}
              value={recipientName}
              onChangeText={setRecipientName}
            />
          </View>

          <View style={styles.formGroup}>
            <ThemedText style={[styles.label, { color: textColor }]}>
              Account Number *
            </ThemedText>
            <TextInput
              style={[styles.input, { color: textColor }]}
              placeholder="Enter account number"
              placeholderTextColor={textColor}
              value={recipientAccount}
              onChangeText={setRecipientAccount}
            />
          </View>
        </ThemedView>

        {/* Amount & Description */}
        <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
          <ThemedText type="subtitle" style={styles.sectionTitle}>
            Transfer Details
          </ThemedText>

          <View style={styles.formGroup}>
            <ThemedText style={[styles.label, { color: textColor }]}>
              Amount ({selectedAccount?.currency || "USD"}) *
            </ThemedText>
            <TextInput
              style={[styles.input, { color: textColor }]}
              placeholder="0.00"
              placeholderTextColor={textColor}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
            />
          </View>

          <View style={styles.formGroup}>
            <ThemedText style={[styles.label, { color: textColor }]}>
              Description (Optional)
            </ThemedText>
            <TextInput
              style={[styles.input, { color: textColor }]}
              placeholder="Add a note"
              placeholderTextColor={textColor}
              value={description}
              onChangeText={setDescription}
              multiline
              numberOfLines={3}
            />
          </View>
        </ThemedView>

        {/* Action Buttons */}
        <View style={styles.buttonContainer}>
          <Pressable
            onPress={handleReviewClick}
            style={({ pressed }) => [
              styles.submitButton,
              { backgroundColor: tintColor },
              pressed && styles.submitButtonPressed,
            ]}
          >
            <ThemedText style={styles.submitButtonText}>Review Transfer</ThemedText>
          </Pressable>

          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [
              styles.cancelButton,
              pressed && styles.cancelButtonPressed,
            ]}
          >
            <ThemedText style={[styles.cancelButtonText, { color: errorColor }]}>
              Cancel
            </ThemedText>
          </Pressable>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          paddingBottom: Math.max(insets.bottom, 20),
        },
      ]}
      contentContainerStyle={{ paddingHorizontal: Math.max(insets.left, 20) }}
    >
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => setStep("form")}>
          <ThemedText style={styles.backButton}>← Back</ThemedText>
        </Pressable>
        <ThemedText type="title">Review Transfer</ThemedText>
      </View>

      {/* Summary */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Transfer Summary
        </ThemedText>

        <View style={styles.summaryRow}>
          <ThemedText style={[styles.summaryLabel, { color: textColor, opacity: 0.6 }]}>
            From
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.summaryValue}>
            {selectedAccount?.accountName}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.summaryRow}>
          <ThemedText style={[styles.summaryLabel, { color: textColor, opacity: 0.6 }]}>
            To
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.summaryValue}>
            {recipientName}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.summaryRow}>
          <ThemedText style={[styles.summaryLabel, { color: textColor, opacity: 0.6 }]}>
            Amount
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={[styles.summaryValue, { color: errorColor }]}>
            -{selectedAccount?.currency} {parseFloat(amount).toFixed(2)}
          </ThemedText>
        </View>

        {description && (
          <>
            <View style={styles.divider} />
            <View style={styles.summaryRow}>
              <ThemedText style={[styles.summaryLabel, { color: textColor, opacity: 0.6 }]}>
                Note
              </ThemedText>
              <ThemedText type="defaultSemiBold" style={styles.summaryValue}>
                {description}
              </ThemedText>
            </View>
          </>
        )}
      </ThemedView>

      {/* Confirmation */}
      <View style={styles.buttonContainer}>
        <Pressable
          onPress={() => setShowBiometricConfirm(true)}
          disabled={createTransactionMutation.isPending}
          style={({ pressed }) => [
            styles.submitButton,
            { backgroundColor: tintColor },
            (pressed || createTransactionMutation.isPending) && styles.submitButtonPressed,
          ]}
        >
          {createTransactionMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <ThemedText style={styles.submitButtonText}>Confirm Transfer</ThemedText>
          )}
        </Pressable>

        <Pressable
          onPress={() => setStep("form")}
          style={({ pressed }) => [
            styles.cancelButton,
            pressed && styles.cancelButtonPressed,
          ]}
        >
          <ThemedText style={[styles.cancelButtonText, { color: errorColor }]}>
            Back
          </ThemedText>
        </Pressable>
      </View>

      {/* Biometric Confirmation Modal */}
      <BiometricConfirmation
        visible={showBiometricConfirm}
        title="Confirm Transfer"
        message={`Transfer ${selectedAccount?.currency} ${parseFloat(amount).toFixed(2)} to ${recipientName}?`}
        amount={`${selectedAccount?.currency} ${parseFloat(amount).toFixed(2)}`}
        onConfirm={handleBiometricConfirm}
        onCancel={() => setShowBiometricConfirm(false)}
        isLoading={createTransactionMutation.isPending}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    marginBottom: 24,
    gap: 12,
  },
  backButton: {
    color: "#0066FF",
    fontSize: 14,
    fontWeight: "600",
  },
  section: {
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 16,
    marginBottom: 12,
  },
  accountSelector: {
    gap: 8,
  },
  accountOption: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
  accountOptionSelected: {
    borderColor: "#0066FF",
    backgroundColor: "rgba(0, 102, 255, 0.05)",
  },
  accountName: {
    fontSize: 14,
    marginBottom: 4,
  },
  accountBalance: {
    fontSize: 12,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "500",
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
  },
  summaryLabel: {
    fontSize: 14,
  },
  summaryValue: {
    fontSize: 14,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0, 0, 0, 0.1)",
  },
  buttonContainer: {
    gap: 12,
    marginBottom: 16,
  },
  submitButton: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  submitButtonPressed: {
    opacity: 0.8,
  },
  submitButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  cancelButton: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 59, 48, 0.3)",
  },
  cancelButtonPressed: {
    opacity: 0.7,
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  quickSelectButton: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: "#0066FF",
    marginBottom: 16,
    alignItems: "center",
    backgroundColor: "rgba(0, 102, 255, 0.05)",
  },
  quickSelectButtonPressed: {
    opacity: 0.7,
  },
  quickSelectText: {
    fontSize: 14,
    fontWeight: "500",
  },
  selectorContainer: {
    marginBottom: 16,
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
  selectorHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0, 0, 0, 0.1)",
  },
  closeSelectorButton: {
    padding: 4,
  },
  closeSelectorText: {
    fontSize: 18,
    color: "#999",
  },
});
