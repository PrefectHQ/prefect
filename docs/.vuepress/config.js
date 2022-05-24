const sidebar1422 = require('../api/0.14.22/sidebar')
const sidebar1513 = require('../api/0.15.13/sidebar')
const glob = require('glob')

// function for loading all MD files in a directory
const getChildren = function (parent_path, dir) {
  return glob
    .sync(parent_path + '/' + dir + '/**/*.md')
    .map(path => {
      // remove "parent_path" and ".md"
      path = path.slice(parent_path.length + 1, -3)
      // remove README
      if (path.endsWith('README')) {
        path = path.slice(0, -6)
      }
      return path
    })
    .sort()
}

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
  extraWatchFiles: ['.vuepress/highlightLines.js'],
  plugins: [
    [
      '@vuepress/google-analytics',
      {
        ga: 'UA-115585378-1'
      }
    ],
    ['vuepress-plugin-code-copy', true],
    ['vuepress-plugin-element-tabs', true],
    [
      'vuepress-plugin-selected-text-popup',
      {
        github: true,
        githubOwner: 'prefecthq',
        githubRepo: 'prefect',
        githubIssueTitle: 'Docs Issue',
        githubTooltipContent: 'Problem with the docs? Create a GitHub Issue!',
        githubLabels: ['docs'],
        twitter: true
      }
    ],
    [
      'sitemap',
      {
        hostname: 'https://docs.prefect.io'
      }
    ]
  ],
  themeConfig: {
    algolia: {
      apiKey: '553c75634e1d4f09c84f7a513f9cc4f9',
      indexName: 'prefect'
    },
    repo: 'PrefectHQ/prefect',
    docsDir: 'docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    logo: '/assets/logomark-gradient.png',
    nav: [
      {
        text: 'Core Engine',
        link: '/core/'
      },
      {
        text: 'Orchestration & API',
        link: '/orchestration/'
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Latest (1.2.2)', link: '/api/latest/' },
          { text: '0.15.13', link: '/api/0.15.13/' },
          { text: '0.14.22', link: '/api/0.14.22/' },
          { text: 'Legacy', link: 'https://docs-legacy.prefect.io' }
        ]
      },
      {
        text: 'prefect.io',
        link: 'https://www.prefect.io'
      },
      {
        text: 'Discourse',
        link: 'https://discourse.prefect.io/'
      }
    ],
    sidebar: {
      '/api/0.14.22/': sidebar1422.sidebar,
      '/api/0.15.13/': sidebar1513.sidebar,
      '/api/latest/': [
        {
          title: 'API Reference',
          path: '/api/latest/'
        },
        'changelog',
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers']
        },
        {
          title: 'prefect.backend',
          collapsable: true,
          children: getChildren('docs/api/latest', 'backend')
        },
        {
          title: 'prefect.client',
          collapsable: true,
          children: getChildren('docs/api/latest', 'client')
        },
        {
          title: 'prefect.cli',
          collapsable: true,
          children: getChildren('docs/api/latest', 'cli')
        },
        {
          title: 'prefect.core',
          collapsable: true,
          children: getChildren('docs/api/latest', 'core')
        },
        {
          title: 'prefect.engine',
          collapsable: true,
          children: getChildren('docs/api/latest', 'engine')
        },
        {
          title: 'prefect.executors',
          collapsable: true,
          children: ['executors.md']
        },
        {
          title: 'prefect.run_configs',
          collapsable: true,
          children: ['run_configs.md']
        },
        {
          title: 'prefect.storage',
          collapsable: true,
          children: ['storage.md']
        },
        {
          title: 'prefect.tasks',
          collapsable: true,
          children: getChildren('docs/api/latest', 'tasks')
        },
        {
          title: 'prefect.schedules',
          collapsable: true,
          children: getChildren('docs/api/latest', 'schedules')
        },
        {
          title: 'prefect.agent',
          collapsable: true,
          children: getChildren('docs/api/latest', 'agent')
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: getChildren('docs/api/latest', 'utilities')
        }
      ],
      '/orchestration/': [
        '/orchestration/',
        {
          title: 'Getting Started',
          collapsable: true,
          children: [
            'getting-started/quick-start',
            'getting-started/install',
            'getting-started/basic-core-flow.md',
            'getting-started/set-up',
            'getting-started/registering-and-running-a-flow',
            'getting-started/next-steps',
            'getting-started/flow-configs',
            'getting-started/more-resources'
          ]
        },
        {
          title: 'Concepts',
          collapsable: true,
          children: [
            'concepts/api',
            'concepts/api_keys',
            'concepts/cli',
            'concepts/flows',
            'concepts/projects',
            'concepts/kv_store',
            'concepts/secrets',
            'concepts/automations',
            'concepts/cloud_hooks',
            'concepts/services',
            'concepts/artifacts'
          ]
        },
        {
          title: 'Flow Configuration',
          collapsable: true,
          children: [
            'flow_config/overview',
            'flow_config/storage',
            'flow_config/run_configs',
            'flow_config/executors',
            'flow_config/docker'
          ]
        },
        {
          title: 'Flow Runs',
          collapsable: true,
          children: [
            'flow-runs/overview',
            'flow-runs/creation',
            'flow-runs/inspection',
            'flow-runs/task-runs',
            'flow-runs/scheduling',
            'flow-runs/setting-states',
            'flow-runs/concurrency-limits'
          ]
        },
        {
          title: 'Agents',
          collapsable: true,
          children: [
            'agents/overview',
            'agents/local',
            'agents/docker',
            'agents/kubernetes',
            'agents/vertex',
            'agents/ecs',
          ]
        },
        {
          title: 'UI',
          collapsable: true,
          children: [
            'ui/dashboard',
            'ui/flow',
            'ui/flow-run',
            'ui/task-run',
            'ui/automations',
            'ui/interactive-api',
            'ui/team-settings'
          ]
        },
        {
          title: 'RBAC',
          collapsable: true,
          children: ['rbac/overview']
        },
        {
          title: 'Server',
          collapsable: true,
          children: [
            'server/overview',
            'server/architecture',
            'server/deploy-local',
            'server/telemetry',
            'server/troubleshooting'
          ]
        },
        {
          title: 'Deployment Recipes',
          collapsable: true,
          children: [
            'recipes/third_party_auth',
            'recipes/configuring_storage',
            'recipes/multi_flow_storage',
            'recipes/k8s_dask',
            'recipes/k8s_docker_sidecar'
          ]
        },
        {
          title: 'Integrations',
          collapsable: true,
          children: ['integrations/pagerduty']
        },
        {
          title: 'FAQ',
          collapsable: true,
          children: getChildren('docs/orchestration', 'faq')
        },
        {
          title: 'Legacy Environments',
          collapsable: true,
          children: [
            'execution/overview',
            'execution/storage_options',
            'execution/local_environment',
            'execution/dask_cloud_provider_environment',
            'execution/dask_k8s_environment',
            'execution/k8s_job_environment',
            'execution/fargate_task_environment',
            'execution/custom_environment'
          ]
        }
      ],
      '/core/': [
        '/core/',
        {
          title: 'About Prefect',
          collapsable: true,
          children: [
            'about_prefect/why-prefect',
            'about_prefect/why-not-airflow',
            'about_prefect/thinking-prefectly',
            'about_prefect/next-steps'
          ]
        },
        {
          title: 'Getting Started',
          collapsable: true,
          children: [
            'getting_started/quick-start',
            'getting_started/install',
            'getting_started/basic-core-flow',
            'getting_started/more-resources'
          ]
        },
        {
          title: ' ETL Tutorial',
          collapsable: true,
          children: getChildren('docs/core', 'tutorial')
        },
        {
          title: 'Core Concepts',
          collapsable: true,
          children: [
            'concepts/tasks',
            'concepts/flows',
            'concepts/parameters',
            'concepts/states',
            'concepts/engine',
            'concepts/execution',
            'concepts/logging',
            'concepts/mapping',
            'concepts/notifications',
            'concepts/persistence',
            'concepts/results',
            'concepts/templating',
            'concepts/schedules',
            'concepts/secrets',
            'concepts/configuration',
            'concepts/best-practices',
            'concepts/common-pitfalls'
          ]
        },
        {
          title: 'Task Library',
          collapsable: true,
          children: ['task_library/overview', 'task_library/contributing']
        },
        {
          title: 'Advanced Tutorials',
          collapsable: true,
          children: getChildren('docs/core', 'advanced_tutorials')
        },
        {
          title: 'Examples',
          collapsable: true,
          children: [
            'examples/overview',
            'examples/parameters',
            'examples/mapping',
            'examples/conditional'
          ]
        },
        {
          title: 'PINs',
          collapsable: true,
          children: getChildren('docs/core', 'PINs')
        },
        {
          title: 'Development',
          collapsable: true,
          children: [
            'development/overview',
            'development/style',
            'development/documentation',
            'development/tests',
            'development/contributing',
            'development/release-checklist',
            'development/sprints'
          ]
        },
        '/core/idioms/idioms',
        '/core/faq',
        '/core/community',
        '/core/code_of_conduct'
      ]
    }
  },
  extendMarkdown(md) {
    md.use(require('./highlightLines.js'))
    md.use(require('markdown-it-attrs'))
    md.use(require('markdown-it-checkbox'))
  }
}
