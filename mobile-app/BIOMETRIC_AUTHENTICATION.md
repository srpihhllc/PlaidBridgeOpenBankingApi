# Biometric Authentication Guide

## Overview

FinBank now includes comprehensive biometric authentication support for both iOS (Face ID/Touch ID) and Android (Fingerprint/Face Recognition). This enhances security and provides a seamless user experience for quick login and transaction confirmation.

## Features

### 1. Biometric Login
- **Quick Authentication**: Users can log in using their biometric credentials instead of entering email and password
- **Fallback Support**: If biometric fails, users can fall back to traditional email login
- **Device Detection**: Automatically detects available biometric methods on the device

### 2. Transaction Confirmation
- **Secure Transfers**: Biometric confirmation required for sending money
- **Two-Step Process**: Review transfer details before biometric confirmation
- **Modal Interface**: Clean, focused confirmation interface

### 3. Biometric Type Detection
- **Face ID** (iOS): Facial recognition authentication
- **Touch ID** (iOS): Fingerprint authentication
- **Fingerprint** (Android): Fingerprint authentication
- **Face Recognition** (Android): Facial recognition authentication

## Implementation Details

### Hook: `useBiometric`

Located in `hooks/use-biometric.ts`, this hook manages all biometric authentication logic.

```typescript
const {
  availability,      // BiometricAvailability object
  isLoading,         // Loading state during availability check
  error,             // Error message if any
  authenticate,      // Function to trigger biometric authentication
  getBiometricType,  // Function to get human-readable biometric type
  checkBiometricAvailability, // Function to recheck availability
} = useBiometric();
```

#### BiometricAvailability Interface

```typescript
interface BiometricAvailability {
  available: boolean;    // Is biometric ready to use?
  compatible: boolean;   // Is device compatible with biometric?
  enrolled: boolean;     // Is biometric enrolled on device?
  types: AuthenticationType[]; // Available authentication types
}
```

### Components

#### BiometricLoginButton

Located in `components/biometric-login-button.tsx`

Renders a button for biometric login when available on the device.

```typescript
<BiometricLoginButton
  onSuccess={() => {
    // Handle successful login
  }}
  onError={(error) => {
    console.error("Biometric login failed:", error);
  }}
/>
```

#### BiometricConfirmation

Located in `components/biometric-confirmation.tsx`

Modal component for transaction confirmation with biometric authentication.

```typescript
<BiometricConfirmation
  visible={showConfirm}
  title="Confirm Transfer"
  message="Transfer $100 to John Doe?"
  amount="$100.00"
  onConfirm={handleConfirm}
  onCancel={handleCancel}
  isLoading={isProcessing}
/>
```

## Usage Examples

### Example 1: Biometric Login

```typescript
import { BiometricLoginButton } from "@/components/biometric-login-button";

export function LoginScreen() {
  const handleBiometricSuccess = async () => {
    // User authenticated via biometric
    // Proceed with login flow
    router.push("/home");
  };

  return (
    <View>
      <BiometricLoginButton
        onSuccess={handleBiometricSuccess}
        onError={(error) => alert(error)}
      />
    </View>
  );
}
```

### Example 2: Transaction Confirmation

```typescript
import { BiometricConfirmation } from "@/components/biometric-confirmation";
import { useBiometric } from "@/hooks/use-biometric";

export function SendMoneyScreen() {
  const { authenticate } = useBiometric();
  const [showBiometricConfirm, setShowBiometricConfirm] = useState(false);

  const handleConfirmTransfer = async () => {
    const success = await authenticate();
    if (success) {
      // Process transaction
      await submitTransaction();
    }
  };

  return (
    <>
      <BiometricConfirmation
        visible={showBiometricConfirm}
        title="Confirm Transfer"
        message="Transfer $100.00 to John Doe?"
        amount="$100.00"
        onConfirm={handleConfirmTransfer}
        onCancel={() => setShowBiometricConfirm(false)}
      />
    </>
  );
}
```

### Example 3: Checking Biometric Availability

```typescript
import { useBiometric } from "@/hooks/use-biometric";

export function SecuritySettings() {
  const { availability, getBiometricType } = useBiometric();

  if (!availability.available) {
    return <Text>Biometric authentication not available</Text>;
  }

  return (
    <Text>
      {getBiometricType()} is available and ready to use
    </Text>
  );
}
```

## Biometric Type Mapping

| Device | Type | Display Name |
|--------|------|--------------|
| iOS | Facial Recognition | Face ID 🔐 |
| iOS | Fingerprint | Touch ID 👆 |
| Android | Fingerprint | Touch ID 👆 |
| Android | Face Recognition | Face ID 🔐 |

## Security Considerations

1. **Device-Level Security**: Biometric authentication leverages the device's secure enclave
2. **No Biometric Storage**: The app never stores biometric data; only the device does
3. **Fallback Mechanism**: Users can always fall back to password-based authentication
4. **Session Management**: Biometric authentication is tied to the current session
5. **Transaction Confirmation**: Critical operations require explicit biometric confirmation

## Error Handling

The biometric system handles various error scenarios:

- **Device Not Compatible**: Shows fallback authentication option
- **Biometric Not Enrolled**: Prompts user to set up biometric
- **Authentication Failed**: Allows retry or fallback
- **Permission Denied**: Gracefully handles permission issues
- **System Errors**: Logs errors and provides user feedback

## Testing

Unit tests are located in `hooks/__tests__/use-biometric.test.ts`

Run tests with:
```bash
pnpm test hooks/__tests__/use-biometric.test.ts
```

Test coverage includes:
- Hardware availability detection
- Biometric enrollment status
- Authentication success/failure
- Error handling
- Biometric type detection
- Multiple biometric types support

## Platform-Specific Notes

### iOS
- Requires Face ID or Touch ID to be set up on the device
- Uses `LocalAuthentication` framework
- Respects system privacy settings

### Android
- Requires biometric hardware (fingerprint sensor or face recognition)
- Uses BiometricPrompt API
- Respects device security settings

## Troubleshooting

### Biometric Button Not Showing
- Check if device has biometric hardware: `availability.compatible`
- Verify biometric is enrolled: `availability.enrolled`
- Check app permissions in device settings

### Authentication Always Fails
- Ensure biometric is properly set up on device
- Try re-enrolling biometric on device
- Check device system logs for errors
- Fall back to password authentication

### Performance Issues
- Biometric check is performed once on app startup
- Use `checkBiometricAvailability()` to refresh if needed
- Authentication typically completes in < 1 second

## Future Enhancements

- [ ] Biometric preference storage in user settings
- [ ] Biometric retry limits and lockout
- [ ] Biometric enrollment guidance
- [ ] Support for iris recognition
- [ ] Biometric analytics and logging

## References

- [Expo Local Authentication](https://docs.expo.dev/modules/local-authentication/)
- [iOS Face ID and Touch ID](https://developer.apple.com/design/human-interface-guidelines/face-id-and-touch-id)
- [Android Biometric API](https://developer.android.com/training/biometric)
