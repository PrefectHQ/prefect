const sidebar81 = require('../api/0.8.1/sidebar')
const sidebar98 = require('../api/0.9.8/sidebar')
const sidebar107 = require('../api/0.10.7/sidebar')
const glob = require('glob')

// function for loading all MD files in a directory
const getChildren = function(parent_path, dir) {
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
    'vuepress-plugin-element-tabs',
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
    logo: '/assets/logomark-color.png',
    nav: [
      {
        text: 'Core',
        link: '/core/'
      },
      {
        text: 'Orchestration',
        link: '/orchestration/'
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Latest (0.11.0)', link: '/api/latest/' },
          { text: '0.10.7', link: '/api/0.10.7/' },
          { text: '0.9.8', link: '/api/0.9.8/' },
          { text: '0.8.1', link: '/api/0.8.1/' },
          { text: 'Legacy', link: 'https://docs-legacy.prefect.io' }
        ]
      },
      {
        text: 'prefect.io',
        link: 'https://www.prefect.io'
      }
    ],
    sidebar: {
      '/api/0.8.1/': sidebar81.sidebar,
      '/api/0.9.8/': sidebar98.sidebar,
      '/api/0.10.7/': sidebar107.sidebar,
      '/api/latest/': [
        {
          title: 'API Reference',
          path: '/api/latest/'
        },
        'changelog',
        {
          title: 'Test Coverage',
          path: 'https://codecov.io/gh/PrefectHQ/prefect'
        },
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers']
        },
        {
          title: 'prefect.client',
          collapsable: true,
          children: getChildren('docs/api/latest', 'client')
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
          title: 'prefect.environments',
          collapsable: true,
          children: getChildren('docs/api/latest', 'environments')
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
          title: 'UI',
          collapsable: true,
          children: [
            'ui/dashboard',
            'ui/flow',
            'ui/flow-run',
            'ui/task-run',
            'ui/interactive-api',
            'ui/team-settings'
          ]
        },
        {
          title: 'Concepts',
          collapsable: true,
          children: [
            'concepts/api',
            'concepts/cli',
            'concepts/projects',
            'concepts/flows',
            'concepts/flow_runs',
            'concepts/cloud_hooks',
            'concepts/secrets',
            'concepts/services',
            'concepts/tokens',
            'concepts/roles',
            'concepts/task-concurrency-limiting'
          ]
        },
        {
          title: 'Deployment Tutorial',
          collapsable: true,
          children: [
            'tutorial/configure',
            'tutorial/first',
            'tutorial/multiple',
            'tutorial/docker',
            'tutorial/k8s',
            'tutorial/next-steps'
          ]
        },
        {
          title: 'Execution Environments',
          collapsable: true,
          children: [
            'execution/overview',
            'execution/storage_options',
            'execution/remote_environment',
            'execution/remote_dask_environment',
            'execution/dask_cloud_provider_environment',
            'execution/dask_k8s_environment',
            'execution/k8s_job_environment',
            'execution/fargate_task_environment',
            'execution/custom_environment'
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
            'agents/fargate'
          ]
        },
        {
          title: 'Deployment Recipes',
          collapsable: true,
          children: [
            'recipes/deployment',
            'recipes/third_party_auth',
            'recipes/configuring_storage',
            'recipes/multi_flow_storage',
            'recipes/k8s_dask',
            'recipes/k8s_docker_sidecar'
          ]
        },
        {
          title: 'Server',
          collapsable: true,
          children: ['server/telemetry']
        },
        {
          title: 'FAQ',
          collapsable: true,
          children: getChildren('docs/orchestration', 'faq')
        }
      ],
      '/core/': [
        '/core/',
        {
          title: 'Getting Started',
          collapsable: true,
          children: [
            'getting_started/installation',
            'getting_started/first-steps',
            'getting_started/next-steps',
            'getting_started/why-prefect',
            'getting_started/why-not-airflow'
          ]
        },
        {
          title: 'Tutorial',
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
          children: getChildren('docs/core', 'task_library')
        },
        {
          title: 'Advanced Tutorials',
          collapsable: true,
          children: getChildren('docs/core', 'advanced_tutorials')
        },
        {
          title: 'Examples',
          collapsable: true,
          children: getChildren('docs/core', 'examples')
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
