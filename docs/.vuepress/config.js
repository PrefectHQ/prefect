const sidebar54 = require("../api/0.5.4/sidebar");
const sidebar60 = require("../api/0.6.0/sidebar");
const sidebar61 = require("../api/0.6.1/sidebar");
const sidebar62 = require("../api/0.6.2/sidebar");
const glob = require("glob");

// function for loading all MD files in a directory
const getChildren = function(parent_path, dir) {
  return glob
    .sync(parent_path + "/" + dir + "/**/*.md")
    .map(path => {
      // remove "parent_path" and ".md"
      path = path.slice(parent_path.length + 1, -3);
      // remove README
      if (path.endsWith("README")) {
        path = path.slice(0, -6);
      }
      return path;
    })
    .sort();
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
        link: "/cloud/first-steps"
      },
      {
        text: "API Reference",
        items: [
          { text: "Unreleased", link: "/api/unreleased/" },
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
      "/api/unreleased/": [
        { title: "API Reference", path: "/api/unreleased/" },
        "changelog",
        "coverage",
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
          title: "prefect.utilities",
          collapsable: true,
          children: getChildren("docs/api/unreleased", "utilities")
        }
      ],
      "/cloud/": [
        {
          title: "Welcome",
          collapsable: false,
          children: ["first-steps", "dataflow", "faq", "upandrunning"]
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
