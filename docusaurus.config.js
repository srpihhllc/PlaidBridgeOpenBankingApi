module.exports = {
  title: 'Financial Powerhouse Platform',
  tagline: 'Unified fintech monorepo documentation',
  url: 'https://yourdomain.com',
  baseUrl: '/',
  favicon: 'img/favicon.ico',

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/edit/main/',
        },
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      },
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'Financial Powerhouse',
      items: [
        { type: 'doc', docId: 'index', position: 'left', label: 'Docs' },
        { href: 'https://github.com/srpihhllc/PlaidBridgeOpenBankingApi', label: 'GitHub', position: 'right' },
      ],
    },
    footer: {
      style: 'dark',
      copyright: `© ${new Date().getFullYear()} Financial Powerhouse Platform`,
    },
  },
};
