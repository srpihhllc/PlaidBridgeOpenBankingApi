import { useMemo, useState } from "react";

export interface TransactionFilters {
  searchQuery: string;
  transactionType: string | null;
  startDate: Date | null;
  endDate: Date | null;
  minAmount: number | null;
  maxAmount: number | null;
}

export interface FilteredTransaction {
  id: number;
  transactionType: string;
  amount: string;
  recipientName: string | null;
  description: string | null;
  status: string;
  createdAt: string | Date;
  currency: string;
  fee: string;
  referenceNumber?: string | null;
  recipientAccount?: string | null;
  updatedAt: string | Date;
}

export function useTransactionFilter(transactions: FilteredTransaction[]) {
  const [filters, setFilters] = useState<TransactionFilters>({
    searchQuery: "",
    transactionType: null,
    startDate: null,
    endDate: null,
    minAmount: null,
    maxAmount: null,
  });

  const filteredTransactions = useMemo(() => {
    return transactions.filter((transaction) => {
      // Search query filter
      if (filters.searchQuery) {
        const query = filters.searchQuery.toLowerCase();
        const matchesSearch =
          transaction.recipientName?.toLowerCase().includes(query) ||
          transaction.description?.toLowerCase().includes(query) ||
          transaction.referenceNumber?.toLowerCase().includes(query) ||
          transaction.amount.includes(query);

        if (!matchesSearch) return false;
      }

      // Transaction type filter
      if (filters.transactionType && filters.transactionType !== "all") {
        if (transaction.transactionType !== filters.transactionType) {
          return false;
        }
      }

      // Date range filter
      if (filters.startDate || filters.endDate) {
        const transactionDate = new Date(transaction.createdAt);

        if (filters.startDate) {
          const startDate = new Date(filters.startDate);
          startDate.setHours(0, 0, 0, 0);
          if (transactionDate < startDate) return false;
        }

        if (filters.endDate) {
          const endDate = new Date(filters.endDate);
          endDate.setHours(23, 59, 59, 999);
          if (transactionDate > endDate) return false;
        }
      }

      // Amount range filter
      if (filters.minAmount !== null || filters.maxAmount !== null) {
        const amount = parseFloat(transaction.amount);

        if (filters.minAmount !== null && amount < filters.minAmount) {
          return false;
        }

        if (filters.maxAmount !== null && amount > filters.maxAmount) {
          return false;
        }
      }

      return true;
    });
  }, [transactions, filters]);

  const updateSearchQuery = (query: string) => {
    setFilters((prev) => ({
      ...prev,
      searchQuery: query,
    }));
  };

  const updateTransactionType = (type: string | null) => {
    setFilters((prev) => ({
      ...prev,
      transactionType: type,
    }));
  };

  const updateDateRange = (startDate: Date | null, endDate: Date | null) => {
    setFilters((prev) => ({
      ...prev,
      startDate,
      endDate,
    }));
  };

  const updateAmountRange = (minAmount: number | null, maxAmount: number | null) => {
    setFilters((prev) => ({
      ...prev,
      minAmount,
      maxAmount,
    }));
  };

  const clearFilters = () => {
    setFilters({
      searchQuery: "",
      transactionType: null,
      startDate: null,
      endDate: null,
      minAmount: null,
      maxAmount: null,
    });
  };

  const hasActiveFilters = () => {
    return (
      filters.searchQuery !== "" ||
      filters.transactionType !== null ||
      filters.startDate !== null ||
      filters.endDate !== null ||
      filters.minAmount !== null ||
      filters.maxAmount !== null
    );
  };

  return {
    filters,
    filteredTransactions,
    updateSearchQuery,
    updateTransactionType,
    updateDateRange,
    updateAmountRange,
    clearFilters,
    hasActiveFilters,
  };
}
