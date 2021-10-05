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
  flows: {
    ids?: string[]
    names?: string[]
    tags?: string[]
  }
  deployments: {
    ids?: string[]
    names?: string[]
    tags?: string[]
  }
  flow_runs: {
    ids?: string[]
    names?: string[]
    tags?: string[]
    states?: RunState[]
    timeframe?: RunTimeFrame
  }
  task_runs: {
    ids?: string[]
    names?: string[]
    tags?: string[]
    states?: RunState[]
    timeframe?: RunTimeFrame
  }
}
