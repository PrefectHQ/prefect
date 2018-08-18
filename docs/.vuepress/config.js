module.exports = {
    title: 'Prefect (Preview)',
    description: "Don't Panic.",
    themeConfig: {
        repo: 'prefecthq/prefect/tree/master/docs',
        editLinks: true,
        // repoLabel: 'GitHub',
        nav: [
            { text: "Overview", link: '/introduction.html' },
            { text: "API", link: '/api/' },
            { text: "License", link: '/license.html' }
        ],
        sidebar: {
            '/api/': [
                '/api/',
                {
                    title: 'prefect',
                    collapsable: true,
                    children: ['environments', 'schedules', 'serializers', 'triggers']
                },

                {
                    title: 'prefect.core',
                    collapsable: true,
                    children: ['core/task', 'core/flow', 'core/edge', 'core/registry']
                },

                {
                    title: 'prefect.engine',
                    collapsable: true,
                    children: ['engine/cache_validators',
                        'engine/executors', 'engine/flow_runner', 'engine/signals',
                        'engine/state', 'engine/task_runner',
                    ]
                },

                {
                    title: 'prefect.tasks',
                    collapsable: true,
                    children: ['tasks/control_flow', 'tasks/function']
                },
                {
                    title: 'prefect.utilities',
                    collapsable: true,
                    children: ['utilities/bokeh', 'utilities/collections', 'utilities/json', 'utilities/tasks']
                },
            ],
            '/license': [],
            '/': ['introduction', 'concepts', 'getting_started',
                {
                    title: 'Tutorials',
                    collapsable: true,
                    children: ['tutorials/', 'tutorials/task-retries', 'tutorials/triggers-and-references']
                },
                'comparisons'
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