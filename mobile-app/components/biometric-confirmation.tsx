import { StyleSheet, View, Pressable, ActivityIndicator, Modal } from "react-native";
import { ThemedText } from "./themed-text";
import { ThemedView } from "./themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useBiometric } from "@/hooks/use-biometric";
import { useState } from "react";

interface BiometricConfirmationProps {
  visible: boolean;
  title: string;
  message: string;
  amount?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function BiometricConfirmation({
  visible,
  title,
  message,
  amount,
  onConfirm,
  onCancel,
  isLoading = false,
}: BiometricConfirmationProps) {
  const { availability, authenticate, getBiometricType } = useBiometric();
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");
  const errorColor = useThemeColor({}, "error");

  const handleBiometricConfirm = async () => {
    if (!availability.available) {
      onConfirm();
      return;
    }

    setIsAuthenticating(true);
    const success = await authenticate();
    setIsAuthenticating(false);

    if (success) {
      onConfirm();
    }
  };

  const biometricType = getBiometricType();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <ThemedView style={[styles.container, { backgroundColor: cardBgColor }]}>
          {/* Header */}
          <ThemedText type="title" style={styles.title}>
            {title}
          </ThemedText>

          {/* Message */}
          <ThemedText style={[styles.message, { color: textColor, opacity: 0.7 }]}>
            {message}
          </ThemedText>

          {/* Amount (if provided) */}
          {amount && (
            <View style={styles.amountContainer}>
              <ThemedText style={[styles.amountLabel, { color: textColor, opacity: 0.6 }]}>
                Amount
              </ThemedText>
              <ThemedText type="title" style={[styles.amount, { color: errorColor }]}>
                {amount}
              </ThemedText>
            </View>
          )}

          {/* Biometric Prompt */}
          {availability.available && (
            <View style={styles.biometricPrompt}>
              <ThemedText style={[styles.biometricText, { color: textColor, opacity: 0.6 }]}>
                Use {biometricType} to confirm
              </ThemedText>
              <ThemedText style={styles.biometricIcon}>
                {biometricType === "Face ID" ? "🔐" : "👆"}
              </ThemedText>
            </View>
          )}

          {/* Action Buttons */}
          <View style={styles.buttonContainer}>
            <Pressable
              onPress={handleBiometricConfirm}
              disabled={isAuthenticating || isLoading}
              style={({ pressed }) => [
                styles.confirmButton,
                { backgroundColor: tintColor },
                (pressed || isAuthenticating || isLoading) && styles.confirmButtonPressed,
              ]}
            >
              {isAuthenticating || isLoading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <ThemedText style={styles.confirmButtonText}>
                  {availability.available ? `Confirm with ${biometricType}` : "Confirm"}
                </ThemedText>
              )}
            </Pressable>

            <Pressable
              onPress={onCancel}
              disabled={isAuthenticating || isLoading}
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
        </ThemedView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  container: {
    borderRadius: 16,
    padding: 24,
    width: "100%",
    maxWidth: 340,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  title: {
    fontSize: 24,
    marginBottom: 12,
    textAlign: "center",
  },
  message: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 20,
    textAlign: "center",
  },
  amountContainer: {
    alignItems: "center",
    marginBottom: 24,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: "rgba(0, 0, 0, 0.1)",
  },
  amountLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  amount: {
    fontSize: 28,
    fontWeight: "700",
  },
  biometricPrompt: {
    alignItems: "center",
    marginBottom: 24,
    paddingVertical: 16,
    backgroundColor: "rgba(0, 102, 255, 0.05)",
    borderRadius: 12,
  },
  biometricText: {
    fontSize: 12,
    marginBottom: 8,
  },
  biometricIcon: {
    fontSize: 32,
  },
  buttonContainer: {
    gap: 12,
  },
  confirmButton: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  confirmButtonPressed: {
    opacity: 0.8,
  },
  confirmButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  cancelButton: {
    paddingVertical: 12,
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
    fontSize: 14,
    fontWeight: "600",
  },
});
