module.exports = {
  title: 'Prefect',
  description: 'Practice Makes Prefect',
  themeConfig: {
    repo: 'prefecthq/prefect/tree/master/docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    nav: [{ text: "Overview", link: '/'},
          { text: "API", link: '/api/' }],
    sidebar: {
      '/api/': [
        {title: 'prefect',
         collapsable: false,
         children: ['', 'environments', 'triggers']},

        {title: 'prefect.core',
         collapsable: false,
         children: ['core/', 'core/edges', 'core/flows']}

      ],
      '/': ['', 'concepts', 'utilities'],
    }
  }
}
