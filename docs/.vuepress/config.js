const webpack = require('webpack')

module.exports = {
  title: 'Prefect (Preview)',
  description: "Don't Panic.",
  head: [
    'link', {
      rel: 'icon',
      href: '/favicon.ico'
    }
  ],
  ga: "UA-115585378-1",
  themeConfig: {
    repo: 'PrefectHQ/prefect/tree/master/docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    logo: '/assets/logomark-color.svg',
    nav: [{
        text: "Guide",
        link: '/guide/'
      },
      {
        text: "API Reference",
        link: '/api/'
      },
      {
        text: "License",
        link: '/license.html'
      },
      {
        text: "Log Out",
        link: '/logout.html'
      }
    ],
    sidebar: {
      '/api/': [
        '/api/',
        'changelog',
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers', 'schedules']
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
          children: [
            'engine/cloud',
            'engine/cache_validators',
            'engine/executors',
            'engine/flow_runner',
            'engine/result',
            'engine/result_handlers',
            'engine/signals',
            'engine/state',
            'engine/task_runner'
          ]
        },
        {
          title: 'prefect.environments',
          collapsable: true,
          children: [
            'environments/environment',
            'environments/base_environment',
            'environments/kubernetes/docker_on_kubernetes',
            'environments/kubernetes/dask_on_kubernetes'
          ]
        },
        {
          title: 'prefect.tasks',
          collapsable: true,
          children: [
            'tasks/airflow',
            'tasks/aws',
            'tasks/control_flow',
            'tasks/function',
            'tasks/google',
            'tasks/shell',
            'tasks/sqlite',
            'tasks/strings'
          ]
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: [
            'utilities/collections',
            'utilities/configuration',
            'utilities/context',
            'utilities/debug',
            'utilities/environments',
            'utilities/executors',
            'utilities/graphql',
            'utilities/logging',
            'utilities/notifications',
            'utilities/serialization',
            'utilities/tasks',
          ]
        }
      ],
      '/license': [],
      '/guide/': [
        '/guide/',
        {
          title: 'Welcome',
          collapsable: false,
          children: [
            'welcome/what_is_prefect',
            'welcome/why_prefect',
            'welcome/prefect_design',
          ]
        },
        {
          title: 'Getting Started',
          collapsable: true,
          children: [
            'getting_started/installation',
            'getting_started/introduction',
            'getting_started/getting_started',
          ]
        },
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
            'core_concepts/results',
            'core_concepts/environments',
            'core_concepts/schedules',
            'core_concepts/configuration',
            'core_concepts/best-practices',
            'core_concepts/common-pitfalls'
          ]
        },
        {
          title: 'Cloud Concepts',
          collapsable: true,
          children: [
            // 'concepts/',
            'cloud_concepts/graphql',
            'cloud_concepts/projects',
            'cloud_concepts/flows',
            'cloud_concepts/schedules',
            'cloud_concepts/flow_runs',
            'cloud_concepts/secrets'
          ]
        },
        {
          title: 'Tutorials',
          collapsable: true,
          children: [

            'tutorials/',
            'tutorials/etl',
            'tutorials/calculator',
            'tutorials/local-debugging',
            'tutorials/task-retries',
            'tutorials/triggers-and-references',
            'tutorials/visualization',
            'tutorials/advanced-mapping',
            'tutorials/airflow_migration',
            'tutorials/slack-notifications'
          ]
        },
        {
          title: 'PINs',
          collapsable: true,
          children: [
            'PINs/',
            'PINs/PIN-1-Introduce-PINs',
            'PINs/PIN-2-Result-Handlers',
            'PINs/PIN-3-Agent-Environment',
            'PINs/PIN-4-Result-Objects',
            'PINs/PIN-5-Combining-Tasks'
          ]
        },
        {
          title: 'Development',
          collapsable: true,
          children: [
            'development/overview',
            'development/style',
            'development/documentation',
            'development/tests',
            'development/contributing'
          ]
        }
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
