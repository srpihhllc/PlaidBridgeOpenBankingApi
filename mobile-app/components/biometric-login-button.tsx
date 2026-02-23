import { StyleSheet, Pressable, ActivityIndicator } from "react-native";
import { ThemedText } from "./themed-text";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useBiometric } from "@/hooks/use-biometric";

interface BiometricLoginButtonProps {
  onSuccess: () => void;
  onError?: (error: string) => void;
}

export function BiometricLoginButton({ onSuccess, onError }: BiometricLoginButtonProps) {
  const { availability, isLoading, authenticate, getBiometricType } = useBiometric();
  const tintColor = useThemeColor({}, "tint");
  const textColor = useThemeColor({}, "text");

  if (isLoading) {
    return (
      <Pressable style={[styles.button, { backgroundColor: tintColor, opacity: 0.6 }]}>
        <ActivityIndicator color="#fff" />
      </Pressable>
    );
  }

  if (!availability.available) {
    return null;
  }

  const handleBiometricLogin = async () => {
    const success = await authenticate();
    if (success) {
      onSuccess();
    } else if (onError) {
      onError("Biometric authentication failed");
    }
  };

  const biometricType = getBiometricType();

  return (
    <Pressable
      onPress={handleBiometricLogin}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: tintColor },
        pressed && styles.buttonPressed,
      ]}
    >
      <ThemedText style={styles.buttonText}>
        {biometricType === "Face ID" ? "🔐" : "👆"} {biometricType}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    marginBottom: 12,
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
});
