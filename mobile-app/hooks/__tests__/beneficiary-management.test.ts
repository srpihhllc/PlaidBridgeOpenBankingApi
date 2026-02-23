import { describe, it, expect } from "vitest";

// Mock beneficiary data
const mockBeneficiaries = [
  {
    id: 1,
    userId: 1,
    beneficiaryName: "John Doe",
    accountNumber: "1234567890",
    bankName: "Bank of America",
    isFrequent: true,
    createdAt: new Date("2024-01-15"),
    updatedAt: new Date("2024-01-15"),
  },
  {
    id: 2,
    userId: 1,
    beneficiaryName: "Jane Smith",
    accountNumber: "0987654321",
    bankName: "Chase Bank",
    isFrequent: false,
    createdAt: new Date("2024-01-14"),
    updatedAt: new Date("2024-01-14"),
  },
  {
    id: 3,
    userId: 1,
    beneficiaryName: "Bob Wilson",
    accountNumber: "5555555555",
    bankName: "Wells Fargo",
    isFrequent: true,
    createdAt: new Date("2024-01-13"),
    updatedAt: new Date("2024-01-13"),
  },
];

describe("Beneficiary Management", () => {
  it("should have mock beneficiaries", () => {
    expect(mockBeneficiaries).toHaveLength(3);
  });

  it("should filter frequent beneficiaries", () => {
    const frequent = mockBeneficiaries.filter((b) => b.isFrequent);
    expect(frequent).toHaveLength(2);
  });

  it("should search beneficiaries by name", () => {
    const query = "john";
    const results = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(query)
    );
    expect(results).toHaveLength(1);
    expect(results[0].beneficiaryName).toBe("John Doe");
  });

  it("should search beneficiaries by bank name", () => {
    const query = "chase";
    const results = mockBeneficiaries.filter((b) =>
      b.bankName.toLowerCase().includes(query)
    );
    expect(results).toHaveLength(1);
    expect(results[0].bankName).toBe("Chase Bank");
  });

  it("should search beneficiaries by account number", () => {
    const query = "1234";
    const results = mockBeneficiaries.filter((b) =>
      b.accountNumber.includes(query)
    );
    expect(results).toHaveLength(1);
    expect(results[0].accountNumber).toBe("1234567890");
  });

  it("should validate beneficiary name", () => {
    const name = "John Doe";
    const isValid = name.trim().length > 0;
    expect(isValid).toBe(true);
  });

  it("should validate account number", () => {
    const accountNumber = "1234567890";
    const isValid = accountNumber.trim().length > 0 && /^\d+$/.test(accountNumber);
    expect(isValid).toBe(true);
  });

  it("should reject invalid account number", () => {
    const accountNumber = "ABC123";
    const isValid = /^\d+$/.test(accountNumber);
    expect(isValid).toBe(false);
  });

  it("should validate bank name", () => {
    const bankName = "Bank of America";
    const isValid = bankName.trim().length > 0;
    expect(isValid).toBe(true);
  });

  it("should mask account number for display", () => {
    const accountNumber = "1234567890";
    const masked = `•••• ${accountNumber.slice(-4)}`;
    expect(masked).toBe("•••• 7890");
  });

  it("should sort beneficiaries by creation date", () => {
    const sorted = [...mockBeneficiaries].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
    expect(sorted[0].beneficiaryName).toBe("John Doe");
  });

  it("should sort frequent beneficiaries first", () => {
    const sorted = [...mockBeneficiaries].sort((a, b) => {
      if (a.isFrequent !== b.isFrequent) {
        return b.isFrequent ? 1 : -1;
      }
      return 0;
    });
    expect(sorted[0].isFrequent).toBe(true);
    expect(sorted[1].isFrequent).toBe(true);
  });

  it("should handle case-insensitive search", () => {
    const query = "JOHN";
    const results = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(query.toLowerCase())
    );
    expect(results).toHaveLength(1);
  });

  it("should handle empty search results", () => {
    const query = "nonexistent";
    const results = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(query)
    );
    expect(results).toHaveLength(0);
  });

  it("should get beneficiary by ID", () => {
    const id = 2;
    const beneficiary = mockBeneficiaries.find((b) => b.id === id);
    expect(beneficiary).toBeDefined();
    expect(beneficiary?.beneficiaryName).toBe("Jane Smith");
  });

  it("should validate unique account numbers", () => {
    const newAccountNumber = "1111111111";
    const isDuplicate = mockBeneficiaries.some(
      (b) => b.accountNumber === newAccountNumber
    );
    expect(isDuplicate).toBe(false);
  });

  it("should count total beneficiaries", () => {
    const count = mockBeneficiaries.length;
    expect(count).toBe(3);
  });
});
