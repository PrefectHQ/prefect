import { InjectionKey } from 'vue'
import { createStore, Store } from 'vuex'
import { GlobalFilter } from '@/typings/global'
import * as getters from './getters'
import * as mutations from './mutations'

export interface State {
  globalFilter: GlobalFilter
}

const state: State = {
  globalFilter: {
    flows: {},
    deployments: {},
    flow_runs: {
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

const actions = {}

export const key: InjectionKey<Store<State>> = Symbol()

const store = createStore<State>({
  state,
  getters,
  mutations,
  actions
})

export default store
