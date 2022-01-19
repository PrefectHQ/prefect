import { GlobalFilter } from '@/typings/global'
import { State } from '.'
import { GetterTree } from 'vuex'
import { calculateStart, calculateEnd } from '@/utilities/timeFrame'

export interface Getters extends GetterTree<State, any> {
  start(state: State): Date
  end(state: State): Date
  globalFilter(state: State): GlobalFilter
}

export const start = (state: State): Date => {
  const timeframe = state.globalFilter.flow_runs.timeframe?.from
  if (!timeframe) return new Date()

  const startDate = calculateStart(timeframe)
  if (!startDate) {
    throw new Error('There was an issue calculating start time in the store.')
  }

  return startDate
}

export const end = (state: State): Date => {
  const timeframe = state.globalFilter.flow_runs.timeframe?.to
  if (!timeframe) return new Date()

  const endDate = calculateEnd(timeframe)
  if (!endDate) {
    throw new Error('There was an issue calculating end time in the store.')
  }

  return endDate
}

export const baseInterval = (state: State, getters: any): number => {
  const seconds = (getters.end.getTime() - getters.start.getTime()) / 1000

  return Math.floor(seconds / 30)
}

export const globalFilter = (state: State): GlobalFilter => state.globalFilter
