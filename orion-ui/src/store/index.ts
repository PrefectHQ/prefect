import { InjectionKey } from 'vue'
import { createStore, Store } from 'vuex'
import { GlobalFilter } from '@/typings/global'
import * as getters from './getters'
import * as mutations from './mutations'

export interface State {
  globalFilter: GlobalFilter
}

const start = new Date()
const end = new Date()

start.setMinutes(start.getMinutes() - 30)
start.setSeconds(0)
start.setMilliseconds(0)
end.setMinutes(end.getMinutes() + 30)
end.setSeconds(0)
end.setMilliseconds(0)

const state: State = {
  globalFilter: {
    end: end,
    object: 'flow_runs',
    intervalSeconds: 60,
    start: start,
    states: [
      { name: 'Scheduled', type: 'SCHEDULED' },
      { name: 'Pending', type: 'PENDING' },
      { name: 'Running', type: 'RUNNING' },
      { name: 'Completed', type: 'COMPLETED' },
      { name: 'Failed', type: 'FAILED' },
      { name: 'Cancelled', type: 'CANCELLED' }
    ],
    tags: [],
    flows: { ids: [], names: [] },
    deployments: { ids: [], names: [] },
    flow_runs: {
      ids: [],
      names: [],
      timeframe: {
        dynamic: true,
        from: {
          value: 60,
          unit: 'minutes'
        },
        to: {
          value: 60,
          unit: 'minutes'
        }
      }
    },
    task_runs: {
      ids: [],
      names: [],
      timeframe: {
        dynamic: true,
        from: {
          value: 60,
          unit: 'minutes'
        },
        to: {
          value: 60,
          unit: 'minutes'
        }
      }
    }
  }
}

const actions = {}

export const key: InjectionKey<Store<State>> = Symbol()

const store = createStore<State>({
  state,
  getters,
  mutations,
  actions
})

export default store
