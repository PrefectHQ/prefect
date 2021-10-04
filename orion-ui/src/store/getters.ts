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
  start(state: State): Date
  end(state: State): Date
  globalFilter(state: State): GlobalFilter
  baseFilter(state: State): (object: string) => UnionFilter
  composedFilter(state: State, getters: GetterTree<State, Getters>): UnionFilter
}

export const start = (state: State): Date => {
  const timeframe = state.globalFilter.flow_runs.timeframe?.from
  if (!timeframe) return new Date()
  if (timeframe.timestamp) return timeframe.timestamp
  if (timeframe.unit && timeframe.value) {
    const date = new Date()

    switch (timeframe.unit) {
      case 'minutes':
        date.setMinutes(date.getMinutes() - timeframe.value)
        break
      case 'hours':
        date.setHours(date.getHours() - timeframe.value)
        break
      case 'days':
        date.setDate(date.getDate() - timeframe.value)
        break
      default:
        break
    }

    return date
  }
  throw new Error('There was an issue calculating start time in the store.')
}

export const end = (state: State): Date => {
  const timeframe = state.globalFilter.flow_runs.timeframe?.to
  if (!timeframe) return new Date()
  if (timeframe.timestamp) return timeframe.timestamp
  if (timeframe.unit && timeframe.value) {
    const date = new Date()

    switch (timeframe.unit) {
      case 'minutes':
        date.setMinutes(date.getMinutes() + timeframe.value)
        break
      case 'hours':
        date.setHours(date.getHours() + timeframe.value)
        break
      case 'days':
        date.setDate(date.getDate() + timeframe.value)
        break
      default:
        break
    }

    return date
  }
  throw new Error('There was an issue calculating start time in the store.')
}

export const baseInterval = (state: State, getters: any): number => {
  return Math.floor(
    (getters.end.getTime() - getters.start.getTime()) / 1000 / 30
  )
}

export const globalFilter = (state: State): GlobalFilter => state.globalFilter

type GlobalFilterKeys = 'flows' | 'deployments' | 'flow_runs' | 'task_runs'
const keys: GlobalFilterKeys[] = [
  'flows',
  'deployments',
  'flow_runs',
  'task_runs'
]

const timeKeys: { [key: string]: 'start_time' | 'expected_start_time' } = {
  task_runs: 'start_time',
  flow_runs: 'expected_start_time'
}

export const baseFilter =
  (state: State) =>
  (object: GlobalFilterKeys): UnionFilter => {
    const timeKey: keyof UnionFilter = timeKeys[object]
    const val: UnionFilter = {
      id: undefined,
      name: undefined,
      tags: undefined,
      [timeKey]: undefined
    }

    if (state.globalFilter[object]?.ids)
      val.id = { any_: state.globalFilter[object].ids }
    if (state.globalFilter[object]?.names)
      val.name = { any_: state.globalFilter[object].names }
    if (state.globalFilter[object]?.tags)
      val.tags = { all_: state.globalFilter[object]?.tags }

    // Break early for flows or deployments
    if (object == 'flows' || object == 'deployments') return val

    const from = state.globalFilter[object]?.timeframe?.from
    const to = state.globalFilter[object]?.timeframe?.to
    const fromExists = from && from.value && from.unit
    const toExists = to && to.value && to.unit

    if (fromExists || toExists) {
      val[timeKey] = {
        before_: undefined,
        after_: undefined
      }
    }

    if (fromExists && from.value) {
      const date = new Date()

      switch (from.unit) {
        case 'minutes':
          date.setMinutes(date.getMinutes() - from.value)
          break
        case 'hours':
          date.setHours(date.getHours() - from.value)
          break
        case 'days':
          date.setDate(date.getDate() - from.value)
          break
        default:
          break
      }

      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      val[timeKey]!.after_ = date.toISOString()
    }

    if (toExists && to.value) {
      const date = new Date()

      switch (to.unit) {
        case 'minutes':
          date.setMinutes(date.getMinutes() + to.value)
          break
        case 'hours':
          date.setHours(date.getHours() + to.value)
          break
        case 'days':
          date.setDate(date.getDate() + to.value)
          break
        default:
          break
      }

      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      val[timeKey]!.before_ = date.toISOString()
    }

    const states = state.globalFilter[object]?.states

    if (states) {
      val['state'] = {
        type: states.reduce<{
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
    }

    Object.entries(val).forEach(([key, value]) => {
      if (!value) delete val[key as keyof UnionFilter]
    })

    return val
  }

/* eslint-disable @typescript-eslint/explicit-module-boundary-types, @typescript-eslint/no-explicit-any */
export const composedFilter = (state: State, getters: any): UnionFilters => {
  //   (object: GlobalFilterKeys): UnionFilters => {
  const val: FlowsFilter | DeploymentsFilter | FlowRunsFilter | TaskRunsFilter =
    {}

  keys.forEach((k) => (val[k] = getters.baseFilter(k)))

  return { ...val }
}
/* eslint-enable @typescript-eslint/explicit-module-boundary-types, @typescript-eslint/no-explicit-any */
