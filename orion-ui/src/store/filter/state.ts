import { GlobalFilter } from '@/typings/global'

export function generateInitialGlobalFilterState(): GlobalFilter {
  return {
    flows: {},
    deployments: {},
    flow_runs: {
      timeframe: {
        dynamic: true,
        from: {
          value: 7,
          unit: 'days'
        },
        to: {
          value: 1,
          unit: 'days'
        }
      },
      states: [
        { name: 'Scheduled', type: 'SCHEDULED' },
        { name: 'Pending', type: 'PENDING' },
        { name: 'Running', type: 'RUNNING' },
        { name: 'Completed', type: 'COMPLETED' },
        { name: 'Failed', type: 'FAILED' },
        { name: 'Cancelled', type: 'CANCELLED' }
      ]
    },
    task_runs: {}
  }
}

export const state = generateInitialGlobalFilterState()
