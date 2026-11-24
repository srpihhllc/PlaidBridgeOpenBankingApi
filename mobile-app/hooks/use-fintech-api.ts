import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as Api from "@/lib/api";



export function useAccounts(enabled = true) {

  return useQuery({

    queryKey: ["fintech", "accounts"],

    queryFn: Api.fetchAccounts,

    enabled,

  });

}



export function useCards(enabled = true) {

  return useQuery({

    queryKey: ["fintech", "cards"],

    queryFn: Api.fetchCards,

    enabled,

  });

}



export function useTransactions(limit = 50, enabled = true) {

  return useQuery({

    queryKey: ["fintech", "transactions", limit],

    queryFn: () => Api.fetchTransactions(limit),

    enabled,

  });

}



export function useCreateTransfer(onSuccess?: () => void) {

  const qc = useQueryClient();

  return useMutation({

    mutationFn: Api.createTransfer,

    onSuccess: () => {

      qc.invalidateQueries({ queryKey: ["fintech", "transactions"] });

      qc.invalidateQueries({ queryKey: ["fintech", "accounts"] });

      onSuccess?.();

    },

  });

}



export function useSignShieldDisclosure() {

  return useMutation({

    mutationFn: Api.signShieldDisclosure,

  });

}





export function useTransactionDetail(id: number | null, enabled = true) {

  return useQuery({

    queryKey: ["fintech", "transaction", id],

    queryFn: () => Api.fetchTransactionById(id as number),

    enabled: enabled && Boolean(id),

  });

}



export function usePreferences(enabled = true) {

  return useQuery({

    queryKey: ["fintech", "preferences"],

    queryFn: Api.fetchPreferences,

    enabled,

  });

}



export function useBeneficiaries(enabled = true) {

  return useQuery({

    queryKey: ["fintech", "beneficiaries"],

    queryFn: Api.fetchBeneficiaries,

    enabled,

  });

}



export function useCreateBeneficiary(options?: {

  onSuccess?: () => void;

  onError?: (err: Error) => void;

}) {

  const qc = useQueryClient();

  return useMutation({

    mutationFn: Api.createBeneficiary,

    onSuccess: () => {

      qc.invalidateQueries({ queryKey: ["fintech", "beneficiaries"] });

      options?.onSuccess?.();

    },

    onError: (err: Error) => options?.onError?.(err),

  });

}



export function useDeleteBeneficiary(options?: { onSuccess?: () => void }) {

  const qc = useQueryClient();

  return useMutation({

    mutationFn: ({ id }: { id: number }) => Api.deleteBeneficiary(id),

    onSuccess: () => {

      qc.invalidateQueries({ queryKey: ["fintech", "beneficiaries"] });

      options?.onSuccess?.();

    },

  });

}

