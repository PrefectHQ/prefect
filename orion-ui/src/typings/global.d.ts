export interface RunState {
  name: string
  type: string
}

export interface RunTimeFrame {
  dynamic: boolean
  from: {
    timestamp?: Date
    unit?: 'minutes' | 'hours' | 'days'
    value?: number
  }
  to: {
    timestamp?: Date
    unit?: 'minutes' | 'hours' | 'days'
    value?: number
  }
}

export interface GlobalFilter {
  end?: Date
  object?: string
  intervalSeconds?: number
  start?: Date
  states: RunState[]
  tags: string[]
  flows: {
    ids: string[]
    names: string[]
  }
  deployments: {
    ids: string[]
    names: string[]
  }
  flow_runs: {
    ids: string[]
    names: string[]
    timeframe: RunTimeFrame
  }
  task_runs: {
    ids: string[]
    names: string[]
    timeframe: RunTimeFrame
  }
}
