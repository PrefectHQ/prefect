const sidebar60 = require('../api/0.6.0/sidebar')
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
  ga: 'UA-115585378-1',
  themeConfig: {
    repo: 'PrefectHQ/prefect',
    docsDir: 'docs',
    editLinks: true,
    // repoLabel: 'GitHub',
    logo: '/assets/logomark-color.svg',
    nav: [
      {
        text: 'Cloud',
        link: '/cloud/first-steps'
      },
      {
        text: 'Core',
        link: '/guide/'
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Unreleased', link: '/api/unreleased/' },
          { text: '0.6.0', link: '/api/0.6.0/' },
        ]
      }
    ],
    sidebar: {
      '/api/0.6.0/': sidebar60.sidebar,
      '/api/unreleased/': [
        '/api/unreleased/',
        'changelog',
        'coverage',
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers']
        },
        {
          title: 'prefect.client',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'client')
        },
        {
          title: 'prefect.core',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'core')
        },
        {
          title: 'prefect.engine',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'engine')
        },
        {
          title: 'prefect.environments',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'environments')
        },
        {
          title: 'prefect.tasks',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'tasks')
        },
        {
          title: 'prefect.schedules',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'schedules')
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'utilities')
        }
      ],
      '/cloud/': [
        {
          title: 'Welcome',
          collapsable: false,
          children: [
            'first-steps',
            'dataflow',
          ]
        },
        {
          title: 'Cloud Concepts',
          collapsable: false,
          children: getChildren('docs/cloud', 'cloud_concepts')
        },
      ],
      '/guide/': [
        '/guide/',
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
          title: 'Tutorials',
          collapsable: true,
          children: getChildren('docs/guide', 'tutorials')
        },
        {
          title: 'Task Library',
          collapsable: true,
          children: getChildren('docs/guide', 'task_library')
        },
        {
          title: 'Core Concepts',
          collapsable: true,
          children: [
            'core_concepts/tasks',
            'core_concepts/flows',
            'core_concepts/parameters',
            'core_concepts/states',
            'core_concepts/mapping',
            'core_concepts/engine',
            'core_concepts/execution',
            'core_concepts/notifications',
            'core_concepts/results',
            'core_concepts/schedules',
            'core_concepts/configuration',
            'core_concepts/best-practices',
            'core_concepts/common-pitfalls'
          ]
        },
        {
          title: 'Examples',
          collapsable: true,
          children: getChildren('docs/guide', 'examples')
        },
        {
          title: 'PINs',
          collapsable: true,
          children: getChildren('docs/guide', 'PINs')
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
  markdown: {
    config: md => {
      md.use(require('markdown-it-attrs'))
      md.use(require('markdown-it-checkbox'))
    }
  }
}
