export interface RunState {
  name: string,
  type: string,
}

export type TimeUnit = 'minutes' | 'hours' | 'days'

export type TimeFrame = {
  timestamp?: Date,
  unit?: TimeUnit,
  value?: number,
}

export interface RunTimeFrame {
  dynamic: boolean,
  from: TimeFrame,
  to: TimeFrame,
}

export interface BaseFilter {
  ids?: string[],
  names?: string[],
  tags?: string[],
}

export interface StatesFilter extends BaseFilter {
  states?: RunState[],
  timeframe?: RunTimeFrame,
}

export interface GlobalFilter {
  flows: BaseFilter,
  deployments: BaseFilter,
  flow_runs: StatesFilter,
  task_runs: StatesFilter,
}