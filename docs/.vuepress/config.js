module.exports = {
    title: 'Prefect (Preview)',
    description: "Don't Panic.",
    themeConfig: {
        repo: 'prefecthq/prefect/tree/master/docs',
        editLinks: true,
        // repoLabel: 'GitHub',
        nav: [{ text: "Overview", link: '/' },
            { text: "API", link: '/api/' }
        ],
        sidebar: {
            '/api/': [{
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
                    children: ['tasks/control_flow']
                },
                {
                    title: 'prefect.utilities',
                    collapsable: true,
                    children: ['utilities/bokeh', 'utilities/collections', 'utilities/json', 'utilities/tasks']
                },
            ],
            '/': ['', 'configuration', 'concepts', 'utilities'],
        }
    },
    markdown: {
        config: md => {
            md.use(require('markdown-it-attrs'))
        }
    }
}