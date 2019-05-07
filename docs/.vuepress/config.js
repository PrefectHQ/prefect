const sidebar50 = require('../api/0.5.0/sidebar')
const sidebar51 = require('../api/0.5.1/sidebar')
const sidebar52 = require('../api/0.5.2/sidebar')
const sidebar53 = require('../api/0.5.3/sidebar')
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
        text: 'Guide',
        link: '/guide/'
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Unreleased', link: '/api/unreleased/' },
          { text: '0.5.3', link: '/api/0.5.3/' },
          { text: '0.5.2', link: '/api/0.5.2/' },
          { text: '0.5.1', link: '/api/0.5.1/' },
          { text: '0.5.0', link: '/api/0.5.0/' }
        ]
      }
    ],
    sidebar: {
      '/api/0.5.3/': sidebar53.sidebar,
      '/api/0.5.2/': sidebar52.sidebar,
      '/api/0.5.1/': sidebar51.sidebar,
      '/api/0.5.0/': sidebar50.sidebar,
      '/api/unreleased/': [
        '/api/unreleased/',
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
          title: 'prefect.utilities',
          collapsable: true,
          children: getChildren('docs/api/unreleased', 'utilities')
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
          title: 'Cloud Concepts',
          collapsable: true,
          children: getChildren('docs/guide', 'cloud_concepts')
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
