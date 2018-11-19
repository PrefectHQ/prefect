const webpack = require('webpack')

module.exports = {
    title: 'Prefect (Preview)',
    description: "Don't Panic.",
    ga: "UA-115585378-1",
    themeConfig: {
        repo: 'PrefectHQ/prefect/tree/master/docs',
        editLinks: true,
        // repoLabel: 'GitHub',
        nav: [{
                text: "Overview",
                link: '/introduction.html'
            },
            {
                text: "API Reference",
                link: '/api/'
            },
            {
                text: "License",
                link: '/license.html'
            }, {
                text: "Log Out",
                link: '/logout.html'
            }
        ],
        sidebar: {
            '/api/': [
                '/api/',
                {
                    title: 'prefect',
                    collapsable: true,
                    children: ['client', 'environments', 'triggers']
                },

                {
                    title: 'prefect.core',
                    collapsable: true,
                    children: ['core/task', 'core/flow', 'core/edge']
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
                    children: ['tasks/control_flow', 'tasks/function', 'tasks/shell', 'tasks/strings']
                },
                {
                    title: 'prefect.utilities',
                    collapsable: true,
                    children: ['utilities/bokeh', 'utilities/collections', 'utilities/executors', 'utilities/tasks', 'utilities/tests', 'utilities/notifications', 'utilities/airflow']
                },
            ],
            '/license': [],
            '/': ['introduction', 'changelog', 'installation', 'getting_started',
                {
                    title: 'Concepts',
                    collapsable: true,
                    children: ['concepts/', 'concepts/core', 'concepts/execution', 'concepts/best-practices']
                },
                {
                    title: 'Tutorials',
                    collapsable: true,
                    children: ['tutorials/', 'tutorials/etl', 'tutorials/calculator', 'tutorials/local-debugging', 'tutorials/task-retries', 'tutorials/triggers-and-references',
                        'tutorials/visualization', 'tutorials/throttling', 'tutorials/advanced-mapping', 'tutorials/airflow_migration', 'tutorials/slack-notifications'
                    ]
                },
                {
                    title: 'Comparisons',
                    collapsable: true,
                    children: ['comparisons/', 'comparisons/airflow']
                },
            ]
        }
    },
    markdown: {
        config: md => {
            md.use(require('markdown-it-attrs'))
            md.use(require('markdown-it-checkbox'))
        }
    },
    configureWebpack: {
        plugins: [
            new webpack.DefinePlugin({
                'process.env.PREFECT_DOCS_DEV_MODE': JSON.stringify(process.env.PREFECT_DOCS_DEV_MODE)
            })
        ]
    }
}
