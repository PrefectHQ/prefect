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
        path: '/api/0.14.22/'
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
        children: getChildren('docs/api/0.14.22', 'backend')
    },
    {
        title: 'prefect.client',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'client')
    },
    {
        title: 'prefect.cli',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'cli')
    },
    {
        title: 'prefect.core',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'core')
    },
    {
        title: 'prefect.engine',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'engine')
    },
    {
        title: 'prefect.environments',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'environments')
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
        children: getChildren('docs/api/0.14.22', 'tasks')
    },
    {
        title: 'prefect.schedules',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'schedules')
    },
    {
        title: 'prefect.agent',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'agent')
    },
    {
        title: 'prefect.artifacts',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'artifacts')
    },
    {
        title: 'prefect.utilities',
        collapsable: true,
        children: getChildren('docs/api/0.14.22', 'utilities')
    }
]

module.exports = {sidebar: sidebar}