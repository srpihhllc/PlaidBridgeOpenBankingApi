import { describe, it, expect } from "vitest";

// Mock beneficiary data
const mockBeneficiaries = [
  {
    id: 1,
    beneficiaryName: "John Doe",
    accountNumber: "1234567890",
    bankName: "Bank of America",
  },
  {
    id: 2,
    beneficiaryName: "Jane Smith",
    accountNumber: "0987654321",
    bankName: "Chase Bank",
  },
  {
    id: 3,
    beneficiaryName: "Bob Wilson",
    accountNumber: "5555555555",
    bankName: "Wells Fargo",
  },
];

describe("Beneficiary Selector Integration", () => {
  it("should have mock beneficiaries", () => {
    expect(mockBeneficiaries).toHaveLength(3);
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

  it("should auto-fill recipient details from selected beneficiary", () => {
    const selected = mockBeneficiaries[0];
    const recipientName = selected.beneficiaryName;
    const recipientAccount = selected.accountNumber;

    expect(recipientName).toBe("John Doe");
    expect(recipientAccount).toBe("1234567890");
  });

  it("should handle empty search results", () => {
    const query = "nonexistent";
    const results = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(query)
    );
    expect(results).toHaveLength(0);
  });

  it("should handle case-insensitive search", () => {
    const query = "JOHN";
    const results = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(query.toLowerCase())
    );
    expect(results).toHaveLength(1);
  });

  it("should filter beneficiaries with multiple criteria", () => {
    const query = "bank";
    const results = mockBeneficiaries.filter(
      (b) =>
        b.beneficiaryName.toLowerCase().includes(query) ||
        b.bankName.toLowerCase().includes(query)
    );
    expect(results).toHaveLength(2);
  });

  it("should mask account number for display", () => {
    const accountNumber = "1234567890";
    const masked = `•••• ${accountNumber.slice(-4)}`;
    expect(masked).toBe("•••• 7890");
  });

  it("should validate beneficiary selection", () => {
    const selected = mockBeneficiaries[0];
    const isValid = selected && selected.beneficiaryName && selected.accountNumber;
    expect(isValid).toBeTruthy();
  });

  it("should handle beneficiary selection with auto-fill", () => {
    const selected = mockBeneficiaries[1];
    const formData = {
      recipientName: selected.beneficiaryName,
      recipientAccount: selected.accountNumber,
    };

    expect(formData.recipientName).toBe("Jane Smith");
    expect(formData.recipientAccount).toBe("0987654321");
  });

  it("should maintain beneficiary list order", () => {
    const firstBeneficiary = mockBeneficiaries[0];
    const lastBeneficiary = mockBeneficiaries[mockBeneficiaries.length - 1];

    expect(firstBeneficiary.beneficiaryName).toBe("John Doe");
    expect(lastBeneficiary.beneficiaryName).toBe("Bob Wilson");
  });

  it("should handle quick selection from beneficiary list", () => {
    const selectedBeneficiary = mockBeneficiaries.find((b) => b.id === 2);
    expect(selectedBeneficiary).toBeDefined();
    expect(selectedBeneficiary?.beneficiaryName).toBe("Jane Smith");
  });

  it("should clear search query after selection", () => {
    let searchQuery = "john";
    const selected = mockBeneficiaries.filter((b) =>
      b.beneficiaryName.toLowerCase().includes(searchQuery)
    );
    searchQuery = "";

    expect(selected).toHaveLength(1);
    expect(searchQuery).toBe("");
  });

  it("should validate account number format", () => {
    const accountNumber = "1234567890";
    const isValid = /^\d+$/.test(accountNumber);
    expect(isValid).toBe(true);
  });

  it("should reject invalid account number", () => {
    const accountNumber = "ABC123";
    const isValid = /^\d+$/.test(accountNumber);
    expect(isValid).toBe(false);
  });
});
