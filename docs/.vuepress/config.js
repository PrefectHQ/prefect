const sidebar73 = require('../api/0.7.3/sidebar')
const sidebar81 = require('../api/0.8.1/sidebar')
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
    logo: '/assets/logomark-color.svg',
    nav: [
      {
        text: 'Prefect Core',
        link: '/core/'
      },
      {
        text: 'Prefect Cloud',
        link: '/cloud/dataflow'
      },
      {
        text: 'API Reference',
        items: [
          {
            text: 'Latest (0.9.3)',
            link: '/api/latest/'
          },
          {
            text: '0.8.1',
            link: '/api/0.8.1/'
          },
          {
            text: '0.7.3',
            link: '/api/0.7.3/'
          },
          {
            text: 'Legacy',
            link: 'https://docs-legacy.prefect.io'
          }
        ]
      }
    ],
    sidebar: {
      '/api/0.7.3/': sidebar73.sidebar,
      '/api/0.8.1/': sidebar81.sidebar,
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
      '/cloud/': [
        {
          title: 'Welcome',
          collapsable: false,
          children: ['dataflow', 'faq']
        },
        {
          title: 'Tutorial',
          collapsable: false,
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
          title: 'Cloud Concepts',
          collapsable: true,
          children: getChildren('docs/cloud', 'concepts')
        },
        {
          title: 'Cloud Execution',
          collapsable: true,
          children: [
            'execution/overview',
            'execution/storage_options',
            'execution/remote_environment',
            'execution/dask_k8s_environment',
            'execution/k8s_job_environment',
            'execution/fargate_task_environment',
            'execution/custom_environment'
          ]
        },
        {
          title: 'Agent',
          collapsable: true,
          children: [
            'agent/overview',
            'agent/local',
            'agent/docker',
            'agent/kubernetes',
            'agent/fargate'
          ]
        },
        {
          title: 'Deployment Recipes',
          collapsable: true,
          children: [
            'recipes/deployment',
            'recipes/configuring_storage',
            'recipes/multi_flow_storage',
            'recipes/k8s_dask',
            'recipes/k8s_docker_sidecar'
          ]
        }
      ],
      '/core/': [
        '/core/',
        {
          title: 'Welcome',
          collapsable: false,
          children: [
            'welcome/what_is_prefect',
            'welcome/why_prefect',
            'welcome/why_not_airflow',
            'welcome/community',
            'welcome/code_of_conduct'
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
            'development/release-checklist'
          ]
        }
      ]
    }
  },
  extendMarkdown(md) {
    md.use(require('./highlightLines.js'))
    md.use(require('markdown-it-attrs'))
    md.use(require('markdown-it-checkbox'))
  }
}
