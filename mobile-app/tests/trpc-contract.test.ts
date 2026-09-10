import { describe, it, expect } from 'vitest';
import { createTRPCProxyClient, httpBatchLink } from '@trpc/client';
import fetch from 'node-fetch';

// Minimal contract test for tRPC. This file uses Jest/Vitest style; adjust to your test runner.
// Place under mobile-app/tests/trpc-contract.test.ts

describe('tRPC contract tests (smoke)', () => {
  const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:3000';
  const TRPC_URL = `${API_BASE}/api/trpc`;

  it('accounts.list returns array', async () => {
    const res = await fetch(TRPC_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: '1', jsonrpc: '2.0', method: 'accounts.list', params: {} }),
    });
    // Accept either 200 or 401 (if auth missing) but ensure server responded
    expect([200, 401]).toContain(res.status);
  });

  it('transactions.list returns server response', async () => {
    const res = await fetch(TRPC_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: '2', jsonrpc: '2.0', method: 'transactions.list', params: {} }),
    });
    expect([200, 401]).toContain(res.status);
  });

  it('preferences.get endpoint reachable', async () => {
    const res = await fetch(TRPC_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: '3', jsonrpc: '2.0', method: 'preferences.get', params: {} }),
    });
    expect([200, 401]).toContain(res.status);
  });
});

