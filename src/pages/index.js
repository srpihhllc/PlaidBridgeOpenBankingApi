import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';

export default function Home() {
  return (
    <Layout
      title="Financial Powerhouse Platform"
      description="Unified fintech monorepo documentation"
    >
      <main style={{ padding: '4rem 1.5rem', maxWidth: 960, margin: '0 auto' }}>
        <h1>Financial Powerhouse Platform</h1>
        <p>
          A unified fintech monorepo combining Flask, React Native / Expo, TRPC, PostgreSQL, Drizzle, and Redis telemetry.
        </p>
        <div style={{ marginTop: '2rem' }}>
          <h2>Start here</h2>
          <ul>
            <li><Link to="/docs/01-system-architecture">System Architecture</Link></li>
            <li><Link to="/docs/05-developer-onboarding">Developer Onboarding</Link></li>
            <li><Link to="/docs/07-operator-handbook">Operator Handbook</Link></li>
            <li><Link to="/docs/09-api-reference">API Reference</Link></li>
          </ul>
        </div>
      </main>
    </Layout>
  );
}
