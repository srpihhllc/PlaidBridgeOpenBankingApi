import { describe, it, expect, beforeEach } from "vitest";

// Mock transaction data
const mockTransactions = [
  {
    id: 1,
    transactionType: "transfer",
    amount: "100.00",
    recipientName: "John Doe",
    description: "Payment for services",
    status: "completed",
    createdAt: "2024-01-15T10:30:00Z",
    currency: "USD",
    fee: "0.50",
  },
  {
    id: 2,
    transactionType: "deposit",
    amount: "500.00",
    recipientName: null,
    description: "Salary deposit",
    status: "completed",
    createdAt: "2024-01-14T09:00:00Z",
    currency: "USD",
    fee: "0.00",
  },
  {
    id: 3,
    transactionType: "withdrawal",
    amount: "50.00",
    recipientName: null,
    description: "ATM withdrawal",
    status: "completed",
    createdAt: "2024-01-13T14:20:00Z",
    currency: "USD",
    fee: "1.00",
  },
  {
    id: 4,
    transactionType: "payment",
    amount: "75.50",
    recipientName: "Jane Smith",
    description: "Bill payment",
    status: "pending",
    createdAt: "2024-01-12T11:15:00Z",
    currency: "USD",
    fee: "0.25",
  },
  {
    id: 5,
    transactionType: "transfer",
    amount: "200.00",
    recipientName: "Bob Wilson",
    description: "Rent payment",
    status: "failed",
    createdAt: "2024-01-11T08:45:00Z",
    currency: "USD",
    fee: "0.50",
  },
];

describe("Transaction Filter Logic", () => {
  it("should have mock transactions", () => {
    expect(mockTransactions).toHaveLength(5);
  });

  it("should filter by transaction type", () => {
    const filtered = mockTransactions.filter((t) => t.transactionType === "transfer");
    expect(filtered).toHaveLength(2);
  });

  it("should filter by amount range", () => {
    const filtered = mockTransactions.filter(
      (t) => parseFloat(t.amount) >= 100 && parseFloat(t.amount) <= 300
    );
    expect(filtered).toHaveLength(2);
  });

  it("should search by recipient name", () => {
    const query = "john";
    const filtered = mockTransactions.filter((t) =>
      t.recipientName?.toLowerCase().includes(query)
    );
    expect(filtered).toHaveLength(1);
  });

  it("should search by description", () => {
    const query = "salary";
    const filtered = mockTransactions.filter((t) =>
      t.description.toLowerCase().includes(query)
    );
    expect(filtered).toHaveLength(1);
  });

  it("should filter by date range", () => {
    const startDate = new Date("2024-01-12T00:00:00Z");
    const endDate = new Date("2024-01-15T23:59:59Z");

    const filtered = mockTransactions.filter((t) => {
      const txDate = new Date(t.createdAt);
      return txDate >= startDate && txDate <= endDate;
    });

    expect(filtered).toHaveLength(4);
  });

  it("should combine multiple filters", () => {
    const typeFilter = "transfer";
    const minAmount = 100;
    const maxAmount = 300;

    const filtered = mockTransactions.filter(
      (t) =>
        t.transactionType === typeFilter &&
        parseFloat(t.amount) >= minAmount &&
        parseFloat(t.amount) <= maxAmount
    );

    expect(filtered).toHaveLength(2);
  });

  it("should handle empty search results", () => {
    const query = "nonexistent";
    const filtered = mockTransactions.filter((t) =>
      t.recipientName?.toLowerCase().includes(query)
    );

    expect(filtered).toHaveLength(0);
  });

  it("should handle case-insensitive search", () => {
    const query = "JOHN";
    const filtered = mockTransactions.filter((t) =>
      t.recipientName?.toLowerCase().includes(query.toLowerCase())
    );

    expect(filtered).toHaveLength(1);
  });

  it("should filter by status", () => {
    const filtered = mockTransactions.filter((t) => t.status === "completed");
    expect(filtered).toHaveLength(3);
  });

  it("should handle minimum amount filter only", () => {
    const minAmount = 100;
    const filtered = mockTransactions.filter((t) => parseFloat(t.amount) >= minAmount);

    expect(filtered).toHaveLength(3);
  });

  it("should handle maximum amount filter only", () => {
    const maxAmount = 100;
    const filtered = mockTransactions.filter((t) => parseFloat(t.amount) <= maxAmount);

    expect(filtered).toHaveLength(3);
  });

  it("should search by amount", () => {
    const query = "100";
    const filtered = mockTransactions.filter((t) => t.amount.includes(query));

    expect(filtered).toHaveLength(1);
  });

  it("should return all transactions when no filters applied", () => {
    expect(mockTransactions).toHaveLength(5);
  });

  it("should handle null recipient names gracefully", () => {
    const filtered = mockTransactions.filter((t) => t.recipientName !== null);
    expect(filtered).toHaveLength(3);
  });
});
