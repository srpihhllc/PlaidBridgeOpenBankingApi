import { StyleSheet, View } from "react-native";
import { ThemedText } from "./themed-text";
import { ThemedView } from "./themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";

interface BalanceCardProps {
  accountName: string;
  balance: string;
  currency?: string;
  accountNumber?: string;
}

export function BalanceCard({
  accountName,
  balance,
  currency = "USD",
  accountNumber,
}: BalanceCardProps) {
  const backgroundColor = useThemeColor({}, "tint");
  const textColor = useThemeColor({ light: "#fff", dark: "#000" }, "text");

  return (
    <ThemedView
      style={[
        styles.card,
        { backgroundColor },
      ]}
    >
      <View style={styles.header}>
        <ThemedText
          type="defaultSemiBold"
          style={[styles.accountName, { color: textColor }]}
        >
          {accountName}
        </ThemedText>
        {accountNumber && (
          <ThemedText style={[styles.accountNumber, { color: textColor, opacity: 0.7 }]}>
            •••• {accountNumber.slice(-4)}
          </ThemedText>
        )}
      </View>

      <View style={styles.balanceContainer}>
        <ThemedText style={[styles.balanceLabel, { color: textColor, opacity: 0.8 }]}>
          Total Balance
        </ThemedText>
        <ThemedText
          type="title"
          style={[styles.balance, { color: textColor }]}
        >
          {currency} {parseFloat(balance).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </ThemedText>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  header: {
    marginBottom: 16,
  },
  accountName: {
    fontSize: 16,
    marginBottom: 4,
  },
  accountNumber: {
    fontSize: 12,
  },
  balanceContainer: {
    gap: 8,
  },
  balanceLabel: {
    fontSize: 14,
  },
  balance: {
    fontSize: 32,
    fontWeight: "700",
  },
});
