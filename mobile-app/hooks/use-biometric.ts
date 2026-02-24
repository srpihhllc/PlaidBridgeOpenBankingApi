import { useEffect, useState } from "react";
import * as LocalAuthentication from "expo-local-authentication";

export interface BiometricAvailability {
  available: boolean;
  compatible: boolean;
  enrolled: boolean;
  types: LocalAuthentication.AuthenticationType[];
}

export function useBiometric() {
  const [availability, setAvailability] = useState<BiometricAvailability>({
    available: false,
    compatible: false,
    enrolled: false,
    types: [],
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkBiometricAvailability();
  }, []);

  const checkBiometricAvailability = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Check if device is compatible with biometric
      const compatible = await LocalAuthentication.hasHardwareAsync();

      if (!compatible) {
        setAvailability({
          available: false,
          compatible: false,
          enrolled: false,
          types: [],
        });
        setIsLoading(false);
        return;
      }

      // Check if biometric is enrolled
      const enrolled = await LocalAuthentication.isEnrolledAsync();

      if (!enrolled) {
        setAvailability({
          available: false,
          compatible: true,
          enrolled: false,
          types: [],
        });
        setIsLoading(false);
        return;
      }

      // Get available biometric types
      const types = await LocalAuthentication.supportedAuthenticationTypesAsync();

      setAvailability({
        available: true,
        compatible: true,
        enrolled: true,
        types,
      });
    } catch (err) {
      console.error("[Biometric] Error checking availability:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
      setAvailability({
        available: false,
        compatible: false,
        enrolled: false,
        types: [],
      });
    } finally {
      setIsLoading(false);
    }
  };

  const authenticate = async (): Promise<boolean> => {
    try {
      if (!availability.available) {
        throw new Error("Biometric authentication not available");
      }

      const result = await LocalAuthentication.authenticateAsync({
        disableDeviceFallback: false,
        fallbackLabel: "Use passcode",
      });

      return result.success;
    } catch (err) {
      console.error("[Biometric] Authentication error:", err);
      setError(err instanceof Error ? err.message : "Authentication failed");
      return false;
    }
  };

  const getBiometricType = (): string => {
    if (!availability.types || availability.types.length === 0) {
      return "Biometric";
    }

    const types = availability.types;
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return "Face ID";
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return "Touch ID";
    }
    if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      return "Iris";
    }

    return "Biometric";
  };

  return {
    availability,
    isLoading,
    error,
    authenticate,
    getBiometricType,
    checkBiometricAvailability,
  };
}
