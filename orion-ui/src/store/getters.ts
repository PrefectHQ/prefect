import { GlobalFilter } from '@/typings/global'
import {
  FlowsFilter,
  DeploymentsFilter,
  FlowRunsFilter,
  TaskRunsFilter
} from '@/plugins/api'
import { State } from '.'
import { GetterTree } from 'vuex'

export type UnionFilter = FlowFilter &
  DeploymentFilter &
  FlowRunFilter &
  TaskRunFilter
export type UnionFilters =
  | FlowsFilter
  | DeploymentsFilter
  | FlowRunsFilter
  | TaskRunsFilter

export interface Getters extends GetterTree<State, any> {
  globalFilter(state: State): GlobalFilter
  baseFilter(state: State): (object: string) => UnionFilter
  composedFilter(state: State, getters: GetterTree<State, Getters>): UnionFilter
}

export const globalFilter = (state: State): GlobalFilter => state.globalFilter

type TimeFilter = { after_?: string; before_?: string } | undefined

type GlobalFilterKeys = 'flows' | 'deployments' | 'flow_runs' | 'task_runs'
const keys: GlobalFilterKeys[] = [
  'flows',
  'deployments',
  'flow_runs',
  'task_runs'
]

export const baseFilter =
  (state: State) =>
  (object: GlobalFilterKeys): UnionFilter => {
    const val: UnionFilter = {}
    if (state.globalFilter[object].ids.length)
      val['id'] = { any_: state.globalFilter[object].ids }
    if (state.globalFilter[object].names.length)
      val['name'] = { any_: state.globalFilter[object].names }
    if (state.globalFilter.tags.length)
      val['tags'] = { all_: state.globalFilter.tags }

    let from, to, start_time: TimeFilter, end_time: TimeFilter

    switch (object) {
      case 'flow_runs':
      case 'task_runs':
        from = state.globalFilter[object].timeframe.from
        to = state.globalFilter[object].timeframe.to

        if (from.value && from.unit) {
          const start = new Date()
          const startDateObjectRef = ('set' +
            from.unit?.[0]?.toUpperCase() +
            from.unit?.slice(1)) as keyof typeof start

          start[startDateObjectRef](from.value)

          start_time = {}
          start_time.after_ = start.toISOString()
          val[object == 'task_runs' ? 'start_time' : 'expected_start_time'] =
            start_time
        }

        if (to.value && to.unit) {
          const end = new Date()
          const startDateObjectRef = ('set' +
            to.unit?.[0]?.toUpperCase() +
            to.unit?.slice(1)) as keyof typeof end

          end[startDateObjectRef](to.value)

          start_time = {}
          start_time.before_ = end.toISOString()
          val[object == 'task_runs' ? 'start_time' : 'expected_start_time'] =
            start_time
        }

        val['state'] = {
          type: state.globalFilter.states.reduce<{
            any_: string[]
          }>(
            (acc, curr) => {
              acc.any_.push(curr.type)
              return acc
            },
            {
              any_: []
            }
          )
        }
        break
      default:
        break
    }

    return val
  }

/* eslint-disable @typescript-eslint/explicit-module-boundary-types, @typescript-eslint/no-explicit-any */
export const composedFilter = (state: State, getters: any): UnionFilters => {
  //   (object: GlobalFilterKeys): UnionFilters => {
  const val: FlowsFilter | DeploymentsFilter | FlowRunsFilter | TaskRunsFilter =
    {}

  const filteredKeys = keys.filter((k) => state.globalFilter.object == k)

  // keys.forEach((k) => (val[k] = getters.baseFilter(k)))
  filteredKeys.forEach((k) => (val[k] = getters.baseFilter(k)))

  return { ...val }
}
/* eslint-enable @typescript-eslint/explicit-module-boundary-types, @typescript-eslint/no-explicit-any */
