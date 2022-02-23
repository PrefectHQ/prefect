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

sidebar = [
    {
        title: 'API Reference',
        path: '/api/0.15.13/'
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
        children: getChildren('docs/api/0.15.13', 'backend')
      },
      {
        title: 'prefect.client',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'client')
      },
      {
        title: 'prefect.cli',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'cli')
      },
      {
        title: 'prefect.core',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'core')
      },
      {
        title: 'prefect.engine',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'engine')
      },
      {
        title: 'prefect.environments',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'environments')
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
        children: getChildren('docs/api/0.15.13', 'tasks')
      },
      {
        title: 'prefect.schedules',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'schedules')
      },
      {
        title: 'prefect.agent',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'agent')
      },
      {
        title: 'prefect.utilities',
        collapsable: true,
        children: getChildren('docs/api/0.15.13', 'utilities')
      }
]

module.exports = {sidebar: sidebar}