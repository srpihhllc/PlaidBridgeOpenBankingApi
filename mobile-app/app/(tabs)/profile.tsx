import { StyleSheet, View, Pressable, ActivityIndicator, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { trpc } from "@/lib/trpc";

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();

  const { data: preferences } = trpc.preferences.get.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");
  const errorColor = useThemeColor({}, "error");

  if (authLoading) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ActivityIndicator size="large" color={tintColor} />
      </ThemedView>
    );
  }

  if (!isAuthenticated) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText type="title">Please log in</ThemedText>
      </ThemedView>
    );
  }

  const handleLogout = async () => {
    await logout();
    router.replace("/");
  };

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
      <ThemedText type="title" style={styles.title}>
        Profile
      </ThemedText>

      {/* User Info Section */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Account Information
        </ThemedText>

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Name
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {user?.name || "Not set"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Email
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {user?.email || "Not set"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            User ID
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {user?.id}
          </ThemedText>
        </View>
      </ThemedView>

      {/* Preferences Section */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Preferences
        </ThemedText>

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Theme
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.theme ? preferences.theme.charAt(0).toUpperCase() + preferences.theme.slice(1) : "Auto"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Language
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.language ? preferences.language.toUpperCase() : "English"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Notifications
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.notificationsEnabled ? "Enabled" : "Disabled"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Biometric
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.biometricEnabled ? "Enabled" : "Disabled"}
          </ThemedText>
        </View>
      </ThemedView>

      {/* Security Section */}
      <ThemedView style={[styles.section, { backgroundColor: cardBgColor }]}>
        <ThemedText type="subtitle" style={styles.sectionTitle}>
          Security
        </ThemedText>

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Two-Factor Authentication
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.twoFactorEnabled ? "Enabled" : "Disabled"}
          </ThemedText>
        </View>

        <View style={styles.divider} />

        <View style={styles.infoRow}>
          <ThemedText style={[styles.infoLabel, { color: textColor, opacity: 0.6 }]}>
            Session Timeout
          </ThemedText>
          <ThemedText type="defaultSemiBold" style={styles.infoValue}>
            {preferences?.sessionTimeout ? `${preferences.sessionTimeout / 60} min` : "15 min"}
          </ThemedText>
        </View>
      </ThemedView>

      {/* Logout Button */}
      <Pressable
        onPress={handleLogout}
        style={({ pressed }) => [
          styles.logoutButton,
          { backgroundColor: errorColor },
          pressed && styles.logoutButtonPressed,
        ]}
      >
        <ThemedText style={styles.logoutText}>Logout</ThemedText>
      </Pressable>

      {/* About Section */}
      <View style={styles.aboutSection}>
        <ThemedText style={[styles.aboutText, { color: textColor, opacity: 0.5 }]}>
          FinBank v1.0.0
        </ThemedText>
        <ThemedText style={[styles.aboutText, { color: textColor, opacity: 0.5 }]}>
          © 2024 Open Fintech Banking
        </ThemedText>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  title: {
    marginBottom: 20,
    paddingHorizontal: 0,
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
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
  },
  infoLabel: {
    fontSize: 14,
  },
  infoValue: {
    fontSize: 14,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0, 0, 0, 0.1)",
    marginVertical: 8,
  },
  logoutButton: {
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  logoutButtonPressed: {
    opacity: 0.8,
  },
  logoutText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  aboutSection: {
    alignItems: "center",
    gap: 4,
    paddingVertical: 16,
  },
  aboutText: {
    fontSize: 12,
    textAlign: "center",
  },
});
