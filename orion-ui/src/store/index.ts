import { InjectionKey } from 'vue'
import { createStore, Store, createLogger } from 'vuex'
import { GlobalFilter } from '@/typings/global'
import * as getters from './getters'
import * as mutations from './mutations'

export interface State {
  globalFilter: GlobalFilter
}

export const initialGlobalFilterState: GlobalFilter = {
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

const state: State = {
  globalFilter: { ...initialGlobalFilterState }
}

const actions = {}

export const key: InjectionKey<Store<State>> = Symbol()

const store = createStore<State>({
  state,
  getters,
  mutations,
  actions,
  plugins: [createLogger()]
})

export default store
