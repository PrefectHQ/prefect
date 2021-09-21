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
  auto_scheduled: boolean
  deployment_id: string
  duration: number
  name: string
  state: string
  tags: string[]
  task_run_count: number
}

export declare interface TaskRun {
  id: string
  flow_run_id: string
  name: string
  start_time: string
  end_time: string
  state_type: string
  state: {
    id: string
    type: string
    message: string
    state_details: { [key: string]: any }
    timestamp: string
    name: string
  }
  duration: number
  sub_flow_run_id: string
  tags: string[]
}
