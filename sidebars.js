module.exports = {
  docs: [
    'index',
    {
      type: 'category',
      label: 'Architecture',
      items: [
        '01-system-architecture',
        '02-platform-overview',
        '03-backend-architecture',
        '04-database-erd',
        '11-monorepo-architecture-diagram'
      ],
    },
    {
      type: 'category',
      label: 'Developer Guides',
      items: [
        '05-developer-onboarding',
        '06-ci-cd-pipeline',
        '07-operator-handbook',
      ],
    },
    {
      type: 'category',
      label: 'References',
      items: [
        '08-release-notes',
        '09-api-reference',
        '10-openapi',
        'CONTRIBUTING',
        'CHANGELOG'
      ],
    },
  ],
};
