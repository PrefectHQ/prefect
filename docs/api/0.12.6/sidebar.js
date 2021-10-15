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

sidebar = [
        { title: "API Reference", path: "/api/0.12.6/" },
        "changelog",
        {
          title: "prefect",
          collapsable: true,
          children: ["triggers"]
        },
        {
          title: "prefect.client",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "client")
        },
        {
          title: "prefect.core",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "core")
        },
        {
          title: "prefect.engine",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "engine")
        },
        {
          title: "prefect.environments",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "environments")
        },
        {
          title: "prefect.tasks",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "tasks")
        },
        {
          title: "prefect.schedules",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "schedules")
        },
        {
          title: "prefect.agent",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "agent")
        },
        {
          title: "prefect.utilities",
          collapsable: true,
          children: getChildren("docs/api/0.12.6", "utilities")
        }
];

module.exports = {sidebar: sidebar}
