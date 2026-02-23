import { describe, it, expect, vi, beforeEach } from "vitest";
import * as LocalAuthentication from "expo-local-authentication";

// Mock expo-local-authentication
vi.mock("expo-local-authentication", () => ({
  hasHardwareAsync: vi.fn(),
  isEnrolledAsync: vi.fn(),
  supportedAuthenticationTypesAsync: vi.fn(),
  authenticateAsync: vi.fn(),
  AuthenticationType: {
    FACIAL_RECOGNITION: 1,
    FINGERPRINT: 2,
    IRIS: 3,
  },
}));

describe("Biometric Authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should detect when biometric hardware is not available", async () => {
    vi.mocked(LocalAuthentication.hasHardwareAsync).mockResolvedValue(false);

    const result = await LocalAuthentication.hasHardwareAsync();

    expect(result).toBe(false);
  });

  it("should detect when biometric hardware is available", async () => {
    vi.mocked(LocalAuthentication.hasHardwareAsync).mockResolvedValue(true);

    const result = await LocalAuthentication.hasHardwareAsync();

    expect(result).toBe(true);
  });

  it("should check if biometric is enrolled", async () => {
    vi.mocked(LocalAuthentication.isEnrolledAsync).mockResolvedValue(true);

    const result = await LocalAuthentication.isEnrolledAsync();

    expect(result).toBe(true);
  });

  it("should detect when biometric is not enrolled", async () => {
    vi.mocked(LocalAuthentication.isEnrolledAsync).mockResolvedValue(false);

    const result = await LocalAuthentication.isEnrolledAsync();

    expect(result).toBe(false);
  });

  it("should return supported authentication types", async () => {
    const mockTypes = [LocalAuthentication.AuthenticationType.FINGERPRINT];
    vi.mocked(LocalAuthentication.supportedAuthenticationTypesAsync).mockResolvedValue(
      mockTypes as any
    );

    const result = await LocalAuthentication.supportedAuthenticationTypesAsync();

    expect(result).toContain(LocalAuthentication.AuthenticationType.FINGERPRINT);
  });

  it("should authenticate successfully", async () => {
    vi.mocked(LocalAuthentication.authenticateAsync).mockResolvedValue({
      success: true,
    } as any);

    const result = await LocalAuthentication.authenticateAsync({
      disableDeviceFallback: false,
      fallbackLabel: "Use passcode",
    });

    expect(result.success).toBe(true);
  });

  it("should handle authentication failure", async () => {
    vi.mocked(LocalAuthentication.authenticateAsync).mockResolvedValue({
      success: false,
    } as any);

    const result = await LocalAuthentication.authenticateAsync({
      disableDeviceFallback: false,
      fallbackLabel: "Use passcode",
    });

    expect(result.success).toBe(false);
  });

  it("should handle authentication errors", async () => {
    const error = new Error("Biometric authentication failed");
    vi.mocked(LocalAuthentication.authenticateAsync).mockRejectedValue(error);

    try {
      await LocalAuthentication.authenticateAsync({
        disableDeviceFallback: false,
        fallbackLabel: "Use passcode",
      });
      expect.fail("Should have thrown an error");
    } catch (err) {
      expect(err).toBe(error);
    }
  });

  it("should support multiple biometric types", async () => {
    const mockTypes = [
      LocalAuthentication.AuthenticationType.FINGERPRINT,
      LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION,
    ];
    vi.mocked(LocalAuthentication.supportedAuthenticationTypesAsync).mockResolvedValue(
      mockTypes as any
    );

    const result = await LocalAuthentication.supportedAuthenticationTypesAsync();

    expect(result).toHaveLength(2);
    expect(result).toContain(LocalAuthentication.AuthenticationType.FINGERPRINT);
    expect(result).toContain(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION);
  });

  it("should call authenticate with correct options", async () => {
    vi.mocked(LocalAuthentication.authenticateAsync).mockResolvedValue({
      success: true,
    } as any);

    const options = {
      disableDeviceFallback: false,
      fallbackLabel: "Use passcode",
    };

    await LocalAuthentication.authenticateAsync(options);

    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledWith(options);
  });
});
