export declare interface Flow {
  id: string
  name: string
  tags: string[]
}

export declare interface Deployment {
  id: string
  name: string
  location: string
  schedule: any
  parameters: { [key: string]: any }[]
  tags: string[]
}

export declare interface FlowRun {
  id: string
  flow_id: string
  deployment_id: string
  duration: number
  name: string
  state: string
  tags: string[]
}

export declare interface TaskRun {
  id: string
  flow_run_id: string
  name: string
  state: string
  duration: number
  sub_flow_run_id: string
  tags: string[]
}
