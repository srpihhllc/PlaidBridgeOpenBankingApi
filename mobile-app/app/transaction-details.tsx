import { StyleSheet, View, Pressable, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { trpc } from "@/lib/trpc";

export default function TransactionDetailsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const transactionId = typeof id === "string" ? parseInt(id) : null;

  const { data: transaction, isLoading, error } = trpc.transactions.get.useQuery(
    { id: transactionId || 0 },
    { enabled: !!transactionId }
  );

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const successColor = useThemeColor({}, "success");
  const errorColor = useThemeColor({}, "error");
  const warningColor = useThemeColor({}, "warning");

  if (isLoading) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText>Loading...</ThemedText>
      </ThemedView>
    );
  }

  if (error || !transaction) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText>Transaction not found</ThemedText>
      </ThemedView>
    );
  }

  const getStatusColor = () => {
    switch (transaction.status) {
      case "completed":
        return successColor;
      case "pending":
        return warningColor;
      case "failed":
      case "cancelled":
        return errorColor;
      default:
        return textColor;
    }
  };

  const isOutgoing = ["transfer", "withdrawal", "payment", "recharge"].includes(transaction.transactionType);
  const amountColor = isOutgoing ? errorColor : successColor;
  const amountPrefix = isOutgoing ? "-" : "+";

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
        <ThemedText type="title">Transaction Details</ThemedText>
      </View>

      {/* Amount Card */}
      <ThemedView style={[styles.amountCard, { backgroundColor: cardBgColor }]}>
        <ThemedText style={[styles.amountLabel, { color: textColor, opacity: 0.6 }]}>
          Amount
        </ThemedText>
        <ThemedText type="title" style={[styles.amount, { color: amountColor }]}>
          {amountPrefix}${parseFloat(transaction.amount).toFixed(2)}
        </ThemedText>
        <ThemedText
          style={[
            styles.status,
            { color: getStatusColor(), marginTop: 12 },
          ]}
        >
          {transaction.status.charAt(0).toUpperCase() + transaction.status.slice(1)}
        </ThemedText>
      </ThemedView>

      {/* Details Section */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Details
        </ThemedText>

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Type
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            {transaction.transactionType.charAt(0).toUpperCase() + transaction.transactionType.slice(1)}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Reference
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            {transaction.referenceNumber || "N/A"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Currency
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            {transaction.currency}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Fee
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            ${parseFloat(transaction.fee).toFixed(2)}
          </ThemedText>
        </View>
      </ThemedView>

      {/* Recipient Section */}
      {transaction.recipientName && (
        <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
          <ThemedText type="subtitle" style={styles.sectionTitle}>
            Recipient
          </ThemedText>

          <View style={styles.detailRow}>
            <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
              Name
            </ThemedText>
            <ThemedText type="defaultSemiBold" style={styles.detailValue}>
              {transaction.recipientName}
            </ThemedText>
          </View>

          {transaction.recipientAccount && (
            <>
              <View style={styles.divider} />
              <View style={styles.detailRow}>
                <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
                  Account
                </ThemedText>
                <ThemedText type="defaultSemiBold" style={styles.detailValue}>
                  ••••{transaction.recipientAccount.slice(-4)}
                </ThemedText>
              </View>
            </>
          )}
        </ThemedView>
      )}

      {/* Timestamp Section */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Timestamp
        </ThemedText>

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Created
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            {new Date(transaction.createdAt).toLocaleString()}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.detailRow}>
          <ThemedText style={[styles.detailLabel, { color: textColor, opacity: 0.6 }]}>
            Updated
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.detailValue}>
            {new Date(transaction.updatedAt).toLocaleString()}
          </ThemedText>
        </View>
      </ThemedView>

      {/* Description */}
      {transaction.description && (
        <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
          <ThemedText type="subtitle" style={styles.sectionTitle}>
            Description
          </ThemedText>
          <ThemedText style={[styles.description, { color: textColor }]}>
            {transaction.description}
          </ThemedText>
        </ThemedView>
      )}
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
  amountCard: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  amountLabel: {
    fontSize: 14,
    marginBottom: 8,
  },
  amount: {
    fontSize: 32,
    fontWeight: "700",
  },
  status: {
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
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
  },
  detailLabel: {
    fontSize: 14,
  },
  detailValue: {
    fontSize: 14,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0, 0, 0, 0.1)",
    marginVertical: 8,
  },
  description: {
    fontSize: 14,
    lineHeight: 20,
  },
});
