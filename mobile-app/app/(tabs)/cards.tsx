import { FlatList, StyleSheet, View, Pressable, ActivityIndicator } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { useThemeColor } from "@/hooks/use-theme-color";
import { useAuth } from "@/hooks/use-auth";
import { trpc } from "@/lib/trpc";

export default function CardsScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated, loading: authLoading } = useAuth();

  const { data: cards = [], isLoading, error } = trpc.cards.list.useQuery(
    undefined,
    { enabled: isAuthenticated }
  );

  const textColor = useThemeColor({}, "text");
  const cardBgColor = useThemeColor({}, "cardBackground");
  const tintColor = useThemeColor({}, "tint");

  if (authLoading || isLoading) {
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

  if (error) {
    return (
      <ThemedView style={[styles.container, { paddingTop: insets.top }]}>
        <ThemedText type="subtitle">Error loading cards</ThemedText>
      </ThemedView>
    );
  }

  const renderCardItem = ({ item }: { item: any }) => (
    <Pressable
      style={({ pressed }) => [
        styles.cardContainer,
        { backgroundColor: tintColor },
        pressed && styles.cardContainerPressed,
      ]}
    >
      <View style={styles.cardContent}>
        <View style={styles.cardTop}>
          <ThemedText style={[styles.cardBrand, { color: "#fff" }]}>
            {item.cardBrand.toUpperCase()}
          </ThemedText>
          <View style={styles.chipIcon}>
            <View style={styles.chip} />
          </View>
        </View>

        <View style={styles.cardMiddle}>
          <ThemedText style={[styles.cardNumber, { color: "#fff" }]}>
            •••• •••• •••• {item.cardNumber.slice(-4)}
          </ThemedText>
        </View>

        <View style={styles.cardBottom}>
          <View>
            <ThemedText style={[styles.cardLabel, { color: "#fff", opacity: 0.7 }]}>
              Card Holder
            </ThemedText>
            <ThemedText style={[styles.cardHolder, { color: "#fff" }]}>
              {item.holderName}
            </ThemedText>
          </View>
          <View style={styles.expiryContainer}>
            <ThemedText style={[styles.cardLabel, { color: "#fff", opacity: 0.7 }]}>
              Expires
            </ThemedText>
            <ThemedText style={[styles.expiry, { color: "#fff" }]}>
              {item.expiryDate}
            </ThemedText>
          </View>
        </View>
      </View>

      <View style={styles.cardStatus}>
        <ThemedText
          style={[
            styles.statusBadge,
            { color: item.status === "active" ? "#34C759" : "#FF3B30" },
          ]}
        >
          {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        </ThemedText>
      </View>
    </Pressable>
  );

  return (
    <ThemedView
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          paddingBottom: Math.max(insets.bottom, 20),
          paddingLeft: Math.max(insets.left, 20),
          paddingRight: Math.max(insets.right, 20),
        },
      ]}
    >
      <ThemedText type="title" style={styles.title}>
        My Cards
      </ThemedText>

      {cards.length === 0 ? (
        <View style={styles.emptyState}>
          <ThemedText type="subtitle">No cards yet</ThemedText>
          <ThemedText style={[styles.emptyStateText, { color: textColor, opacity: 0.6 }]}>
            Add a card to start making payments
          </ThemedText>
        </View>
      ) : (
        <FlatList
          data={cards}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderCardItem}
          scrollEnabled={false}
          contentContainerStyle={styles.listContent}
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  title: {
    marginBottom: 20,
  },
  listContent: {
    gap: 16,
  },
  cardContainer: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  cardContainerPressed: {
    opacity: 0.9,
  },
  cardContent: {
    gap: 16,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  cardBrand: {
    fontSize: 16,
    fontWeight: "700",
  },
  chipIcon: {
    width: 40,
    height: 32,
    justifyContent: "center",
    alignItems: "center",
  },
  chip: {
    width: 32,
    height: 24,
    backgroundColor: "rgba(255, 255, 255, 0.3)",
    borderRadius: 4,
  },
  cardMiddle: {
    gap: 8,
  },
  cardNumber: {
    fontSize: 18,
    fontWeight: "500",
    letterSpacing: 2,
  },
  cardBottom: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  cardLabel: {
    fontSize: 10,
    marginBottom: 2,
  },
  cardHolder: {
    fontSize: 12,
    fontWeight: "600",
  },
  expiryContainer: {
    alignItems: "flex-end",
  },
  expiry: {
    fontSize: 12,
    fontWeight: "600",
  },
  cardStatus: {
    alignItems: "flex-end",
    marginTop: 8,
  },
  statusBadge: {
    fontSize: 12,
    fontWeight: "600",
  },
  emptyState: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
  },
  emptyStateText: {
    fontSize: 14,
    textAlign: "center",
  },
});
