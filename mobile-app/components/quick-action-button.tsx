import { StyleSheet, Pressable, View } from "react-native";
import { ThemedText } from "./themed-text";
import { useThemeColor } from "@/hooks/use-theme-color";

interface QuickActionButtonProps {
  icon: string;
  label: string;
  onPress: () => void;
}

export function QuickActionButton({ icon, label, onPress }: QuickActionButtonProps) {
  const tintColor = useThemeColor({}, "tint");
  const textColor = useThemeColor({}, "text");

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        pressed && styles.buttonPressed,
      ]}
    >
      <View
        style={[
          styles.iconContainer,
          { backgroundColor: tintColor },
        ]}
      >
        <ThemedText style={styles.icon}>{icon}</ThemedText>
      </View>
      <ThemedText style={[styles.label, { color: textColor }]}>
        {label}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  buttonPressed: {
    opacity: 0.7,
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  icon: {
    fontSize: 24,
  },
  label: {
    fontSize: 12,
    fontWeight: "500",
    textAlign: "center",
  },
});
