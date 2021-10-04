import { GlobalFilter, RunState, RunTimeFrame } from '@/typings/global'
import { State } from '.'

export const globalFilter = (state: State, g: GlobalFilter): void => {
  state.globalFilter = g
}

export const states = (
  state: State,
  payload: { object: 'task_runs' | 'flow_runs'; states: RunState[] }
): void => {
  state.globalFilter[payload.object].states = payload.states
}

interface TimeFramePayload extends RunTimeFrame {
  object: 'flow_runs' | 'task_runs'
}

export const timeframe = (state: State, timeframe: TimeFramePayload): void => {
  state.globalFilter[timeframe.object].timeframe = {
    dynamic: timeframe.dynamic,
    from: timeframe.from,
    to: timeframe.to
  }
}
