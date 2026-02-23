import { View, Pressable, StyleSheet } from "react-native";
import { ThemedText } from "./themed-text";
import { useThemeColor } from "@/hooks/use-theme-color";

export interface AlertBannerProps {
  id: number;
  title: string;
  message: string;
  type: "warning" | "info" | "success" | "error";
  severity?: "low" | "medium" | "high" | "critical";
  onDismiss?: (id: number) => void;
  actionLabel?: string;
  onAction?: () => void;
}

export function AlertBanner({
  id,
  title,
  message,
  type,
  severity = "medium",
  onDismiss,
  actionLabel,
  onAction,
}: AlertBannerProps) {
  const backgroundColor = useThemeColor({}, "background");
  const textColor = useThemeColor({}, "text");

  // Determine colors based on alert type
  const getAlertColors = () => {
    switch (type) {
      case "warning":
        return {
          bgColor: "#FFF3CD",
          borderColor: "#FFE69C",
          textColor: "#856404",
          iconColor: "⚠️",
        };
      case "error":
        return {
          bgColor: "#F8D7DA",
          borderColor: "#F5C6CB",
          textColor: "#721C24",
          iconColor: "❌",
        };
      case "success":
        return {
          bgColor: "#D4EDDA",
          borderColor: "#C3E6CB",
          textColor: "#155724",
          iconColor: "✅",
        };
      case "info":
      default:
        return {
          bgColor: "#D1ECF1",
          borderColor: "#BEE5EB",
          textColor: "#0C5460",
          iconColor: "ℹ️",
        };
    }
  };

  const colors = getAlertColors();

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.bgColor,
          borderLeftColor: colors.borderColor,
        },
      ]}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <ThemedText
            style={[styles.icon, { color: colors.textColor }]}
          >
            {colors.iconColor}
          </ThemedText>
          <ThemedText
            type="defaultSemiBold"
            style={[styles.title, { color: colors.textColor }]}
          >
            {title}
          </ThemedText>
        </View>
        <ThemedText
          style={[styles.message, { color: colors.textColor, opacity: 0.9 }]}
        >
          {message}
        </ThemedText>

        {(actionLabel || onDismiss) && (
          <View style={styles.actions}>
            {actionLabel && onAction && (
              <Pressable
                onPress={onAction}
                style={({ pressed }) => [
                  styles.actionButton,
                  { backgroundColor: colors.textColor },
                  pressed && styles.actionButtonPressed,
                ]}
              >
                <ThemedText
                  style={[styles.actionText, { color: colors.bgColor }]}
                >
                  {actionLabel}
                </ThemedText>
              </Pressable>
            )}
            {onDismiss && (
              <Pressable
                onPress={() => onDismiss(id)}
                style={({ pressed }) => [
                  styles.dismissButton,
                  pressed && styles.dismissButtonPressed,
                ]}
              >
                <ThemedText
                  style={[styles.dismissText, { color: colors.textColor }]}
                >
                  Dismiss
                </ThemedText>
              </Pressable>
            )}
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderLeftWidth: 4,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    marginHorizontal: 16,
  },
  content: {
    gap: 8,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  icon: {
    fontSize: 18,
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
  },
  message: {
    fontSize: 13,
    lineHeight: 18,
  },
  actions: {
    flexDirection: "row",
    gap: 8,
    marginTop: 8,
  },
  actionButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    alignItems: "center",
  },
  actionButtonPressed: {
    opacity: 0.8,
  },
  actionText: {
    fontSize: 12,
    fontWeight: "600",
  },
  dismissButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1,
  },
  dismissButtonPressed: {
    opacity: 0.7,
  },
  dismissText: {
    fontSize: 12,
    fontWeight: "500",
  },
});
