const sidebar54 = require('../api/0.5.4/sidebar')
const sidebar60 = require('../api/0.6.0/sidebar')
const sidebar61 = require('../api/0.6.1/sidebar')
const sidebar62 = require('../api/0.6.2/sidebar')
const sidebar64 = require('../api/0.6.4/sidebar')
const sidebar65 = require('../api/0.6.5/sidebar')
const sidebar66 = require('../api/0.6.6/sidebar')
const sidebar67 = require('../api/0.6.7/sidebar')
const sidebar70 = require('../api/0.7.0/sidebar')
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
};

module.exports = {
  title: "Prefect Docs",
  description: "Don't Panic.",
  head: [
    "link",
    {
      rel: "icon",
      href: "/favicon.ico"
    }
  ],
  plugins: [
    [
      "@vuepress/google-analytics",
      {
        ga: "UA-115585378-1"
      }
    ],
    ["vuepress-plugin-code-copy", true]
  ],
  themeConfig: {
    algolia: {
      apiKey: '553c75634e1d4f09c84f7a513f9cc4f9',
      indexName: 'prefect'
    },
    repo: "PrefectHQ/prefect",
    docsDir: "docs",
    editLinks: true,
    // repoLabel: 'GitHub',
    logo: "/assets/logomark-color.svg",
    nav: [
      {
        text: "Prefect Core",
        link: "/core/"
      },
      {
        text: "Prefect Cloud",
        link: "/cloud/the-basics"
      },
      {
        text: "API Reference",
        items: [
          { text: "Unreleased", link: "/api/unreleased/" },
          { text: "0.7.0", link: "/api/0.7.0/" },
          { text: "0.6.7", link: "/api/0.6.7/" },
          { text: "0.6.6", link: "/api/0.6.6/" },
          { text: "0.6.5", link: "/api/0.6.5/" },
          { text: "0.6.4", link: "/api/0.6.4/" },
          { text: "0.6.2 / 0.6.3", link: "/api/0.6.2/" },
          { text: "0.6.1", link: "/api/0.6.1/" },
          { text: "0.6.0", link: "/api/0.6.0/" },
          { text: "0.5.4", link: "/api/0.5.4/" }
        ]
      }
    ],
    sidebar: {
      "/api/0.5.4/": sidebar54.sidebar,
      "/api/0.6.0/": sidebar60.sidebar,
      "/api/0.6.1/": sidebar61.sidebar,
      "/api/0.6.2/": sidebar62.sidebar,
      "/api/0.6.4/": sidebar64.sidebar,
      "/api/0.6.5/": sidebar65.sidebar,
      "/api/0.6.6/": sidebar66.sidebar,
      "/api/0.6.7/": sidebar67.sidebar,
      "/api/0.7.0/": sidebar70.sidebar,
      "/api/unreleased/": [
        { title: "API Reference", path: "/api/unreleased/" },
        "changelog",
        { title: "Test Coverage", path: "https://codecov.io/gh/PrefectHQ/prefect" },
        {
          title: "prefect",
          collapsable: true,
          children: ["triggers"]
        },
        {
          title: "prefect.client",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "client")
        },
        {
          title: "prefect.core",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "core")
        },
        {
          title: "prefect.engine",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "engine")
        },
        {
          title: "prefect.environments",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "environments")
        },
        {
          title: "prefect.tasks",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "tasks")
        },
        {
          title: "prefect.schedules",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "schedules")
        },
        {
          title: "prefect.agent",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "agent")
        },
        {
          title: "prefect.utilities",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "utilities")
        }
      ],
      "/cloud/": [
        {
          title: "Welcome",
          collapsable: false,
          children: ["the-basics", "upandrunning", "flow-deploy", "dataflow", "deployment", "faq"]
        },
        {
          title: "Cloud Concepts",
          collapsable: true,
          children: getChildren('docs/cloud', 'concepts')
        },
        {
          title: 'Agent',
          collapsable: true,
          children: [
            'agent/overview',
            'agent/local',
            'agent/kubernetes',
            'agent/fargate',
          ]
        },
      ],
      "/core/": [
        "/core/",
        {
          title: "Welcome",
          collapsable: false,
          children: [
            "welcome/what_is_prefect",
            "welcome/why_prefect",
            "welcome/why_not_airflow",
            "welcome/community",
            "welcome/code_of_conduct"
          ]
        },
        {
          title: "Getting Started",
          collapsable: true,
          children: [
            "getting_started/installation",
            "getting_started/first-steps",
            "getting_started/next-steps"
          ]
        },
        {
          title: "Tutorials",
          collapsable: true,
          children: getChildren("docs/core", "tutorials")
        },
        {
          title: "Task Library",
          collapsable: true,
          children: getChildren("docs/core", "task_library")
        },
        {
          title: "Core Concepts",
          collapsable: true,
          children: [
            "concepts/tasks",
            "concepts/flows",
            "concepts/parameters",
            "concepts/states",
            "concepts/mapping",
            "concepts/engine",
            "concepts/execution",
            "concepts/persistence",
            "concepts/notifications",
            "concepts/results",
            "concepts/schedules",
            "concepts/configuration",
            "concepts/best-practices",
            "concepts/common-pitfalls"
          ]
        },
        {
          title: "Examples",
          collapsable: true,
          children: getChildren("docs/core", "examples")
        },
        {
          title: "PINs",
          collapsable: true,
          children: getChildren("docs/core", "PINs")
        },
        {
          title: "Development",
          collapsable: true,
          children: [
            "development/overview",
            "development/style",
            "development/documentation",
            "development/tests",
            "development/contributing",
            "development/release-checklist"
          ]
        }
      ]
    }
  },
  extendMarkdown(md) {
    md.use(require("markdown-it-attrs"));
    md.use(require("markdown-it-checkbox"));
  }
};
