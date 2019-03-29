sidebar = [
        '/api/0.5.0/',
        {
          title: 'prefect',
          collapsable: true,
          children: ['triggers', 'schedules']
        },
        {
          title: 'prefect.client',
          collapsable: true,
          children: ['client/client', 'client/secrets']
        },
        {
          title: 'prefect.core',
          collapsable: true,
          children: ['core/task', 'core/flow', 'core/edge']
        },
        {
          title: 'prefect.engine',
          collapsable: true,
          children: [
            'engine/cloud',
            'engine/cache_validators',
            'engine/executors',
            'engine/flow_runner',
            'engine/result',
            'engine/result_handlers',
            'engine/signals',
            'engine/state',
            'engine/task_runner'
          ]
        },
        {
          title: 'prefect.environments',
          collapsable: true,
          children: [
            'environments/environment',
            'environments/base_environment',
            'environments/kubernetes/docker_on_kubernetes',
            'environments/kubernetes/dask_on_kubernetes'
          ]
        },
        {
          title: 'prefect.tasks',
          collapsable: true,
          children: [
            'tasks/airflow',
            'tasks/aws',
            'tasks/collections',
            'tasks/constants',
            'tasks/control_flow',
            'tasks/docker',
            'tasks/function',
            'tasks/github',
            'tasks/google',
            'tasks/kubernetes',
            'tasks/notifications',
            'tasks/operators',
            'tasks/rss',
            'tasks/shell',
            'tasks/sqlite',
            'tasks/strings'
          ]
        },
        {
          title: 'prefect.utilities',
          collapsable: true,
          children: [
            'utilities/collections',
            'utilities/configuration',
            'utilities/context',
            'utilities/debug',
            'utilities/environments',
            'utilities/executors',
            'utilities/graphql',
            'utilities/logging',
            'utilities/notifications',
            'utilities/serialization',
            'utilities/tasks'
          ]
        }
      ]

module.exports = {sidebar: sidebar}
