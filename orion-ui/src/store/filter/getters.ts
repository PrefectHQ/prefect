import { GetterTree } from 'vuex'
import { calculateStart, calculateEnd } from '@/utilities/timeFrame'
import type { RootState } from '@/store'
import { GlobalFilter } from '@/typings/global'

export const getters: GetterTree<GlobalFilter, RootState> = {
  baseInterval(state: GlobalFilter, getters): number {
    const seconds = (getters.end.getTime() - getters.start.getTime()) / 1000

    return Math.floor(seconds / 30)
  },
  start(state: GlobalFilter): Date {
    const timeframe = state.flow_runs.timeframe?.from
    if (!timeframe) return new Date()

    const startDate = calculateStart(timeframe)
    if (!startDate) {
      throw new Error('There was an issue calculating start time in the store.')
    }

    return startDate
  },
  end(state: GlobalFilter): Date {
    const timeframe = state.flow_runs.timeframe?.to
    if (!timeframe) return new Date()

    const endDate = calculateEnd(timeframe)
    if (!endDate) {
      throw new Error('There was an issue calculating end time in the store.')
    }

    return endDate
  }
}
