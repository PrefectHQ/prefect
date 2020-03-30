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
        { title: "API Reference", path: "/api/0.9.8/" },
        "changelog",
        {
          title: "prefect",
          collapsable: true,
          children: ["triggers"]
        },
        {
          title: "prefect.client",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "client")
        },
        {
          title: "prefect.core",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "core")
        },
        {
          title: "prefect.engine",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "engine")
        },
        {
          title: "prefect.environments",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "environments")
        },
        {
          title: "prefect.tasks",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "tasks")
        },
        {
          title: "prefect.schedules",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "schedules")
        },
        {
          title: "prefect.agent",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "agent")
        },
        {
          title: "prefect.utilities",
          collapsable: true,
          children: getChildren("docs/api/0.9.8", "utilities")
        }
];

module.exports = {sidebar: sidebar}
