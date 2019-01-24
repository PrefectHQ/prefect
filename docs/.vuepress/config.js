const webpack = require('webpack')

module.exports = {
  title: 'Prefect (Preview)',
  description: "Don't Panic.",
  ga: "UA-115585378-1",
  themeConfig: {
    repo: 'PrefectHQ/prefect/tree/master/docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    nav: [{
        text: "Overview",
        link: '/introduction.html'
      },
      {
        text: "API Reference",
        link: '/api/'
      },
      {
        text: "License",
        link: '/license.html'
      }, {
        text: "Log Out",
        link: '/logout.html'
      }
    ],
    sidebar: {
      '/api/': [
        '/api/',
        {
          title: 'prefect',
          collapsable: true,
          children: ['environments', 'triggers', 'schedules']
        },

        {
          title: 'prefect.client',
          collapsable: true,
          children: ['client/client', 'client/secrets']
        },

        {
          title: 'prefect.core',
          collapsable: true,
          children: ['core/task', 'core/flow', 'core/edge']
        },

        {
          title: 'prefect.engine',
          collapsable: true,
          children: ['engine/cache_validators',
            'engine/executors', 'engine/flow_runner', 'engine/signals',
            'engine/state', 'engine/task_runner',
          ]
        },

        {
          title: 'prefect.tasks',
          collapsable: true,
          children: ['tasks/control_flow', 'tasks/function', 'tasks/shell', 'tasks/sqlite', 'tasks/strings']
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: [
            'utilities/bokeh',
            'utilities/collections',
            'utilities/configuration',
            'utilities/context',
            'utilities/debug',
            'utilities/executors',
            'utilities/graphql',
            'utilities/logging',
            'utilities/notifications',
            'utilities/serialization',
            'utilities/tasks',
            'utilities/airflow'
          ]
        },
      ],
      '/license': [],
      '/': ['introduction', 'changelog', 'installation', 'getting_started',
        {
          title: 'Core Concepts',
          collapsable: true,
          children: [
            // 'concepts/',
            'core_concepts/tasks',
            'core_concepts/flows',
            'core_concepts/parameters',
            'core_concepts/states',
            'core_concepts/mapping',
            'core_concepts/engine',
            'core_concepts/execution',
            'core_concepts/environments',
            'core_concepts/schedules',
            'core_concepts/best-practices',
            'core_concepts/common-pitfalls'
          ]
        },{
          title: 'Cloud Concepts',
          collapsable: true,
          children: [
            // 'concepts/',
            'cloud_concepts/graphql',
            'cloud_concepts/projects',
            'cloud_concepts/flows',
            'cloud_concepts/schedules',
            'cloud_concepts/flow_runs',
          ]
        },
        {
          title: 'Tutorials',
          collapsable: true,
          children: ['tutorials/', 'tutorials/etl', 'tutorials/calculator', 'tutorials/local-debugging', 'tutorials/task-retries', 'tutorials/triggers-and-references',
            'tutorials/visualization', 'tutorials/advanced-mapping', 'tutorials/airflow_migration', 'tutorials/slack-notifications'
          ]
        },
        {
          title: 'PINs',
          collapsable: true,
          children: ['PINs/', 'PINs/1-record-architecture-decisions']
        },
        {
          title: 'Comparisons',
          collapsable: true,
          children: ['comparisons/', 'comparisons/airflow']
        },
      ]
    }
  },
  markdown: {
    config: md => {
      md.use(require('markdown-it-attrs'))
      md.use(require('markdown-it-checkbox'))
    }
  },
  configureWebpack: {
    plugins: [
      new webpack.DefinePlugin({
        'process.env.PREFECT_DOCS_DEV_MODE': JSON.stringify(process.env.PREFECT_DOCS_DEV_MODE)
      })
    ]
  }
}
