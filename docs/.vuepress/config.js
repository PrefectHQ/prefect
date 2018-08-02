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
         collapsable: true,
         children: ['client', 'environments', 'schedules', 'serializers', 'triggers'] 
        },

        {title: 'prefect.core',
         collapsable: true,
         children: ['core/edge', 'core/flow', 'core/task']},

        {title: 'prefect.engine',
        collapsable: true,
        children: ['engine/cache_validators', 'engine/flow_runner', 'engine/signals',
                    'engine/state', 'engine/task_runner',
                    'engine/executors/base', 'engine/executors/local', 'engine/executors/dask']},

        {title: 'prefect.utilities',
         collapsable: true,
         children: ['utilities/collections', 'utilities/tasks', 'utilities/flows']},
      ],
      '/': ['', 'configuration', 'concepts', 'utilities'],
    }
  }
}
