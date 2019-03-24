module.exports = {
  title: 'Prefect Docs',
  description: "Don't Panic.",
  head: [
    'link',
    {
      rel: 'icon',
      href: '/favicon.ico'
    }
  ],
  ga: 'UA-115585378-1',
  themeConfig: {
    repo: 'PrefectHQ/prefect',
    docsDir: 'docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    logo: '/assets/logomark-color.svg',
    nav: [
      {
        text: 'Guide',
        link: '/guide/'
      },
      {
        text: 'API Reference',
        link: '/api/'
      }
    ],
    sidebar: {
      '/api/': [
        '/api/',
        'changelog',
        'coverage',
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
            'tasks/collections',
            'tasks/constants',
            'tasks/control_flow',
            'tasks/function',
            'tasks/github',
            'tasks/google',
            'tasks/kubernetes',
            'tasks/notifications',
            'tasks/operators',
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
            'utilities/tasks'
          ]
        }
      ],
      '/guide/': [
        '/guide/',
        {
          title: 'Welcome',
          collapsable: false,
          children: [
            'welcome/what_is_prefect',
            'welcome/why_prefect',
            'welcome/community',
            'welcome/prefect_design'
          ]
        },
        {
          title: 'Getting Started',
          collapsable: true,
          children: [
            'getting_started/installation',
            'getting_started/first-steps',
            'getting_started/next-steps'
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
            'tutorials/visualization',
            'tutorials/advanced-mapping',
            'tutorials/slack-notifications'
          ]
        },
        {
          title: 'Task Library',
          collapsable: true,
          children: [
            'task_library/',
            'task_library/airflow',
            'task_library/airtable',
            'task_library/aws',
            'task_library/collections',
            'task_library/constants',
            'task_library/control_flow',
            'task_library/function',
            'task_library/github',
            'task_library/google',
            'task_library/kubernetes',
            'task_library/notifications',
            'task_library/operators',
            'task_library/shell',
            'task_library/sqlite',
            'task_library/strings',
            'task_library/twitter'
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
            'core_concepts/notifications',
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
            'cloud_concepts/auth',
            'cloud_concepts/ui',
            'cloud_concepts/graphql',
            'cloud_concepts/projects',
            'cloud_concepts/flows',
            'cloud_concepts/flow_runs',
            'cloud_concepts/scheduled-flows',
            'cloud_concepts/secrets'
          ]
        },
        {
          title: 'Examples',
          collapsable: true,
          children: [
            'examples/airflow_tutorial_dag',
            'examples/etl',
            'examples/github_release_cycle',
            'examples/map_reduce',
            'examples/parameterized_flow',
            'examples/retries_with_mapping',
            'examples/twitter_to_airtable',
            'examples/daily_github_stats_to_airtable'
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
  }
}
