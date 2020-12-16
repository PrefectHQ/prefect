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
        { title: "API Reference", path: "/api/0.13.19/" },
        "changelog",
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers']
        },
        {
          title: 'prefect.client',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'client')
        },
        {
          title: 'prefect.cli',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'cli')
        },
        {
          title: 'prefect.core',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'core')
        },
        {
          title: 'prefect.engine',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'engine')
        },
        {
          title: 'prefect.environments',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'environments')
        },
        {
          title: 'prefect.run_configs',
          collapsable: true,
          children: ['run_configs.md'],
        },
        {
          title: 'prefect.tasks',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'tasks')
        },
        {
          title: 'prefect.schedules',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'schedules')
        },
        {
          title: 'prefect.agent',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'agent')
        },
        {
          title: 'prefect.artifacts',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'artifacts')
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: getChildren('docs/api/0.13.19', 'utilities')
        }
];

module.exports = {sidebar: sidebar}
