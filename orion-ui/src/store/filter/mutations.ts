import { MutationTree } from 'vuex'
import { GlobalFilter, RunState, RunTimeFrame } from '@/typings/global'
import { generateInitialGlobalFilterState } from './state'

interface TimeFramePayload extends RunTimeFrame {
  object: 'flow_runs' | 'task_runs'
}

export const mutations: MutationTree<GlobalFilter> = {
  setFilter(state: GlobalFilter, filter: GlobalFilter) {
    if (filter.deployments) {
      state.deployments = { ...filter.deployments }
    }
    if (filter.flow_runs) {
      state.flow_runs = { ...filter.flow_runs }
    }
    if (filter.flows) {
      state.flows = { ...filter.flows }
    }
    if (filter.task_runs) {
      state.task_runs = { ...filter.task_runs }
    }
  },
  resetFilter(state: GlobalFilter) {
    const defaults = generateInitialGlobalFilterState()

    state.deployments = defaults.deployments
    state.flow_runs = defaults.flow_runs
    state.flows = defaults.flows
    state.task_runs = defaults.task_runs
  },
  states(
    state: GlobalFilter,
    payload: { object: 'task_runs' | 'flow_runs'; states: RunState[] }
  ) {
    state[payload.object].states = payload.states
  },
  tags(
    state: GlobalFilter,
    payload: {
      object: 'task_runs' | 'flow_runs' | 'deployments' | 'flows'
      tags: string[]
    }
  ) {
    state[payload.object].tags = payload.tags
  },
  timeframe(state: GlobalFilter, timeframe: TimeFramePayload) {
    state[timeframe.object].timeframe = {
      dynamic: timeframe.dynamic,
      from: timeframe.from,
      to: timeframe.to
    }
  }
}
