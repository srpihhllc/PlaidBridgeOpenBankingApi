import React, { useState, useCallback } from "react";
import { Button, Modal, View, ActivityIndicator, StyleSheet, Alert } from "react-native";
import { WebView, WebViewMessageEvent } from "react-native-webview";
import { apiCall } from "@/lib/api";

/**
 * Plaid Link via WebView (Expo-friendly)
 *
 * - Fetches link_token from backend: POST /create_link_token
 * - Loads Plaid Link in WebView using the returned link_token
 * - On success, receives public_token via window.ReactNativeWebView.postMessage
 * - Sends public_token to backend: POST /exchange_public_token
 *
 * Notes:
 * - Ensure your backend API_BASE is set (EXPO_PUBLIC_API_BASE_URL) or use ngrok.
 * - If backend endpoints differ, change the two paths below.
 */

const CREATE_LINK_TOKEN_PATH = "/create_link_token"; // adjust if your API path differs
const EXCHANGE_PUBLIC_TOKEN_PATH = "/exchange_public_token";

export default function PlaidLinkButton() {
  const [visible, setVisible] = useState(false);
  const [html, setHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const generatePlaidHtml = (linkToken: string) => {
    // Minimal HTML page that initializes Plaid Link and posts messages back to RN WebView
    const tpl = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Plaid Link</title>
        </head>
        <body>
          <div id="root">
            <p>Opening Plaid Link…</p>
          </div>
          <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
          <script>
            (function() {
              try {
                const handler = Plaid.create({
                  token: "${linkToken}",
                  onSuccess: function(public_token, metadata) {
                    const payload = { type: "success", public_token: public_token, metadata: metadata };
                    window.ReactNativeWebView.postMessage(JSON.stringify(payload));
                  },
                  onExit: function(err, metadata) {
                    const payload = { type: "exit", error: err ? (err.display_message || err.error_message || err.message) : null, metadata: metadata };
                    window.ReactNativeWebView.postMessage(JSON.stringify(payload));
                  },
                  onEvent: function(eventName, metadata) {
                    // Optionally post events for debugging
                    // window.ReactNativeWebView.postMessage(JSON.stringify({type: "event", eventName, metadata}));
                  }
                });
                handler.open();
              } catch (e) {
                window.ReactNativeWebView.postMessage(JSON.stringify({ type: "fatal", error: String(e) }));
              }
            })();
          </script>
        </body>
      </html>
    `;
    return tpl;
  };

  const onOpen = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiCall<{ link_token?: string; error?: string }>(CREATE_LINK_TOKEN_PATH, {
        method: "POST",
      });
      if ((resp as any).error) {
        throw new Error((resp as any).error || "No link_token returned");
      }
      const linkToken = (resp as any).link_token;
      if (!linkToken) throw new Error("No link_token returned from backend");
      setHtml(generatePlaidHtml(linkToken));
      setVisible(true);
    } catch (err) {
      Alert.alert("Error creating Plaid Link token", String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const onMessage = useCallback(async (e: WebViewMessageEvent) => {
    try {
      const data = JSON.parse(e.nativeEvent.data);
      if (!data || !data.type) return;
      if (data.type === "success") {
        setVisible(false);
        const publicToken = data.public_token;
        // exchange public_token on backend
        const exch = await apiCall<{ access_token?: string; item_id?: string; error?: string }>(
          EXCHANGE_PUBLIC_TOKEN_PATH,
          {
            method: "POST",
            body: JSON.stringify({ public_token: publicToken }),
          }
        );
        if ((exch as any).error) {
          Alert.alert("Exchange failed", String((exch as any).error));
          return;
        }
        Alert.alert("Bank linked", "Account linked successfully.");
      } else if (data.type === "exit") {
        setVisible(false);
        if (data.error) {
          Alert.alert("Plaid exited", String(data.error));
        }
      } else if (data.type === "fatal") {
        setVisible(false);
        Alert.alert("Plaid error", String(data.error));
      }
    } catch (err) {
      setVisible(false);
      Alert.alert("Plaid message parse error", String(err));
    }
  }, []);

  return (
    <View style={styles.container}>
      {loading ? (
        <ActivityIndicator />
      ) : (
        <Button title="Connect bank" onPress={onOpen} />
      )}

      <Modal visible={visible} animationType="slide" onRequestClose={() => setVisible(false)}>
        <View style={styles.webviewContainer}>
          {html ? (
            <WebView
              originWhitelist={["*"]}
              source={{ html }}
              onMessage={onMessage}
              javaScriptEnabled
              startInLoadingState
              allowsInlineMediaPlayback
            />
          ) : (
            <ActivityIndicator style={styles.loader} />
          )}
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  webviewContainer: {
    flex: 1,
  },
  loader: {
    marginTop: 20,
  },
});
