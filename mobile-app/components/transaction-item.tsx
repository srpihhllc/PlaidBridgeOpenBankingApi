import { StyleSheet, View, Pressable } from "react-native";
import { ThemedText } from "./themed-text";
import { ThemedView } from "./themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";

interface TransactionItemProps {
  id: number;
  type: "transfer" | "deposit" | "withdrawal" | "payment" | "recharge";
  amount: string;
  recipientName?: string;
  description?: string;
  status: "pending" | "completed" | "failed" | "cancelled";
  date: Date;
  onPress?: () => void;
}

export function TransactionItem({
  id,
  type,
  amount,
  recipientName,
  description,
  status,
  date,
  onPress,
}: TransactionItemProps) {
  const textColor = useThemeColor({}, "text");
  const successColor = useThemeColor({}, "success");
  const errorColor = useThemeColor({}, "error");
  const warningColor = useThemeColor({}, "warning");

  const getTransactionIcon = () => {
    switch (type) {
      case "transfer":
        return "→";
      case "deposit":
        return "↓";
      case "withdrawal":
        return "↑";
      case "payment":
        return "💳";
      case "recharge":
        return "📱";
      default:
        return "•";
    }
  };

  const getTransactionColor = () => {
    if (status === "failed") return errorColor;
    if (status === "pending") return warningColor;
    if (type === "deposit") return successColor;
    return textColor;
  };

  const getTransactionLabel = () => {
    switch (type) {
      case "transfer":
        return "Transfer";
      case "deposit":
        return "Deposit";
      case "withdrawal":
        return "Withdrawal";
      case "payment":
        return "Payment";
      case "recharge":
        return "Recharge";
      default:
        return "Transaction";
    }
  };

  const isOutgoing = type === "transfer" || type === "withdrawal" || type === "payment" || type === "recharge";
  const amountColor = isOutgoing ? errorColor : successColor;
  const amountPrefix = isOutgoing ? "-" : "+";

  return (
    <Pressable onPress={onPress}>
      <ThemedView style={styles.container}>
        <View style={styles.iconContainer}>
          <ThemedText style={[styles.icon, { color: getTransactionColor() }]}>
            {getTransactionIcon()}
          </ThemedText>
        </View>

        <View style={styles.content}>
          <ThemedText type="defaultSemiBold" style={styles.label}>
            {getTransactionLabel()}
          </ThemedText>
          <ThemedText style={[styles.description, { color: textColor, opacity: 0.6 }]}>
            {recipientName || description || "Transaction"}
          </ThemedText>
          <ThemedText style={[styles.date, { color: textColor, opacity: 0.5 }]}>
            {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </ThemedText>
        </View>

        <View style={styles.amountContainer}>
          <ThemedText
            type="defaultSemiBold"
            style={[styles.amount, { color: amountColor }]}
          >
            {amountPrefix}${parseFloat(amount).toFixed(2)}
          </ThemedText>
          <ThemedText style={[styles.status, { color: getTransactionColor() }]}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </ThemedText>
        </View>
      </ThemedView>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E5EA",
    gap: 12,
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "rgba(0, 102, 255, 0.1)",
    justifyContent: "center",
    alignItems: "center",
  },
  icon: {
    fontSize: 20,
  },
  content: {
    flex: 1,
    gap: 4,
  },
  label: {
    fontSize: 14,
  },
  description: {
    fontSize: 12,
  },
  date: {
    fontSize: 11,
  },
  amountContainer: {
    alignItems: "flex-end",
    gap: 4,
  },
  amount: {
    fontSize: 14,
  },
  status: {
    fontSize: 11,
  },
});
