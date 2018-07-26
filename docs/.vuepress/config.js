module.exports = {
  title: 'Prefect',
  description: 'Practice Makes Prefect',
  themeConfig: {
    repo: 'prefecthq/prefect/docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    sidebar: [
      {title: 'Overview',
       collapsable: false,
       children: [
                  '/',
                  'concepts',
                  'utilities'
                 ]},
      {title: 'API Documentation',
       collapsable: true,
       children: [
                  'api/environments',
                  'api/triggers'
                 ]}
    ]
  }
}
