/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import { Platform } from "react-native";

const tintColorLight = "#0066FF";
const tintColorDark = "#00D4FF";

export const Colors = {
  light: {
    text: "#1C1C1E",
    background: "#FFFFFF",
    tint: "#0066FF",
    icon: "#8E8E93",
    tabIconDefault: "#8E8E93",
    tabIconSelected: "#0066FF",
    success: "#34C759",
    warning: "#FF9500",
    error: "#FF3B30",
    cardBackground: "#F5F5F7",
    divider: "#E5E5EA",
  },
  dark: {
    text: "#F5F5F7",
    background: "#000000",
    tint: "#00D4FF",
    icon: "#A1A1A6",
    tabIconDefault: "#A1A1A6",
    tabIconSelected: "#00D4FF",
    success: "#34C759",
    warning: "#FF9500",
    error: "#FF3B30",
    cardBackground: "#1C1C1E",
    divider: "#38383A",
  },
};

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: "system-ui",
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: "ui-serif",
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: "ui-rounded",
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: "ui-monospace",
  },
  default: {
    sans: "normal",
    serif: "serif",
    rounded: "normal",
    mono: "monospace",
  },
  web: {
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    serif: "Georgia, 'Times New Roman', serif",
    rounded: "'SF Pro Rounded', 'Hiragino Maru Gothic ProN', Meiryo, 'MS PGothic', sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
});
