import {
  StyleSheet,
  View,
  TextInput,
  Pressable,
  ActivityIndicator,
  ScrollView,
  Alert,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useState } from "react";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { trpc } from "@/lib/trpc";

export default function AddBeneficiaryScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const textColor = useThemeColor({}, "text");
  const tintColor = useThemeColor({}, "tint");

  const [name, setName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [bankName, setBankName] = useState("");

  const createMutation = trpc.beneficiaries.create.useMutation({
    onSuccess: () => {
      Alert.alert("Success", "Beneficiary added successfully");
      router.back();
    },
    onError: (error) => {
      Alert.alert("Error", error.message || "Failed to add beneficiary");
    },
  });

  const handleAddBeneficiary = () => {
    if (!name.trim() || !accountNumber.trim() || !bankName.trim()) {
      Alert.alert("Validation Error", "Please fill in all fields");
      return;
    }

    createMutation.mutate({
      beneficiaryName: name,
      accountNumber,
      bankName,
    });
  };

  return (
    <ThemedView
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          paddingBottom: Math.max(insets.bottom, 20),
        },
      ]}
    >
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backButton}>
            <ThemedText style={styles.backButtonText}>← Back</ThemedText>
          </Pressable>
          <ThemedText type="title">Add Beneficiary</ThemedText>
          <View style={styles.spacer} />
        </View>

        {/* Form */}
        <View style={styles.form}>
          {/* Name Field */}
          <View style={styles.formGroup}>
            <ThemedText style={styles.label}>Beneficiary Name</ThemedText>
            <TextInput
              style={[styles.input, { color: textColor, borderColor: tintColor }]}
              placeholder="Enter name"
              placeholderTextColor={textColor}
              value={name}
              onChangeText={setName}
              editable={!createMutation.isPending}
            />
          </View>

          {/* Account Number Field */}
          <View style={styles.formGroup}>
            <ThemedText style={styles.label}>Account Number</ThemedText>
            <TextInput
              style={[styles.input, { color: textColor, borderColor: tintColor }]}
              placeholder="Enter account number"
              placeholderTextColor={textColor}
              value={accountNumber}
              onChangeText={setAccountNumber}
              editable={!createMutation.isPending}
            />
          </View>

          {/* Bank Name Field */}
          <View style={styles.formGroup}>
            <ThemedText style={styles.label}>Bank Name</ThemedText>
            <TextInput
              style={[styles.input, { color: textColor, borderColor: tintColor }]}
              placeholder="Enter bank name"
              placeholderTextColor={textColor}
              value={bankName}
              onChangeText={setBankName}
              editable={!createMutation.isPending}
            />
          </View>


        </View>
      </ScrollView>

      {/* Action Buttons */}
      <View style={styles.actions}>
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [styles.cancelButton, pressed && styles.buttonPressed]}
          disabled={createMutation.isPending}
        >
          <ThemedText style={styles.cancelButtonText}>Cancel</ThemedText>
        </Pressable>

        <Pressable
          onPress={handleAddBeneficiary}
          style={({ pressed }) => [styles.submitButton, pressed && styles.buttonPressed]}
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <ThemedText style={styles.submitButtonText}>Add Beneficiary</ThemedText>
          )}
        </Pressable>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 16,
  },
  scrollContent: {
    flexGrow: 1,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  backButton: {
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  backButtonText: {
    fontSize: 14,
    color: "#0066FF",
  },
  spacer: {
    width: 40,
  },
  form: {
    gap: 20,
    marginBottom: 24,
  },
  formGroup: {
    gap: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: "500",
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 12,
    fontSize: 14,
  },
  checkboxContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 8,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: "#ccc",
    justifyContent: "center",
    alignItems: "center",
  },
  checkmark: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "bold",
  },
  checkboxLabel: {
    fontSize: 14,
  },
  actions: {
    flexDirection: "row",
    gap: 12,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
    alignItems: "center",
  },
  submitButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: "#0066FF",
    alignItems: "center",
  },
  buttonPressed: {
    opacity: 0.7,
  },
  cancelButtonText: {
    fontSize: 14,
    fontWeight: "600",
  },
  submitButtonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
});
