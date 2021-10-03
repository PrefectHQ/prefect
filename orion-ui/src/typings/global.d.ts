export interface RunState {
  name: string
  type: string
}

export interface GlobalFilter {
  end?: Date
  object?: string
  intervalSeconds?: number
  start?: Date
  states?: RunState[]
}
