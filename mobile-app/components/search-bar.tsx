import { StyleSheet, TextInput, View, Pressable } from "react-native";
import { ThemedText } from "./themed-text";
import { useThemeColor } from "@/hooks/use-theme-color";

interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  onClear?: () => void;
  placeholder?: string;
}

export function SearchBar({
  value,
  onChangeText,
  onClear,
  placeholder = "Search transactions...",
}: SearchBarProps) {
  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");

  return (
    <View style={[styles.container, { backgroundColor: cardBgColor }]}>
      <View style={styles.inputWrapper}>
        <ThemedText style={styles.icon}>🔍</ThemedText>
        <TextInput
          style={[styles.input, { color: textColor }]}
          placeholder={placeholder}
          placeholderTextColor={textColor}
          value={value}
          onChangeText={onChangeText}
          clearButtonMode="never"
        />
        {value.length > 0 && onClear && (
          <Pressable onPress={onClear} style={styles.clearButton}>
            <ThemedText style={styles.clearIcon}>✕</ThemedText>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  icon: {
    fontSize: 18,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 8,
    paddingHorizontal: 0,
  },
  clearButton: {
    padding: 4,
  },
  clearIcon: {
    fontSize: 16,
    opacity: 0.5,
  },
});
