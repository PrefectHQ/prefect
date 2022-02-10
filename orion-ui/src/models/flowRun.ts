import { State } from '@prefecthq/orion-design'
import { State as StateObj } from '@/typings/objects'

export interface IFlowRun {
  id: string
  deployment_id: string
  flow_id: string
  flow_version: string
  idempotency_key: string | null
  next_scheduled_start_time: string | null
  parameters: unknown
  auto_scheduled: boolean
  context: unknown
  emperical_config: unknown
  emperical_policy: unknown
  estimated_run_time: number
  estimated_start_time_delta: number
  total_run_time: number
  start_time: Date
  end_time: Date
  name: string
  parent_task_run_id: string
  state_id: string
  state_type: State
  state: StateObj
  tags: string[]
  task_run_count: number
  updated: Date
}

export default class FlowRun implements IFlowRun {
  public readonly id: string
  public readonly deployment_id: string
  public readonly flow_id: string
  public flow_version: string
  public idempotency_key: string | null
  public next_scheduled_start_time: string | null
  public parameters: unknown
  public auto_scheduled: boolean
  public context: unknown
  public emperical_config: unknown
  public emperical_policy: unknown
  public estimated_run_time: number
  public estimated_start_time_delta: number
  public total_run_time: number
  public start_time: Date
  public end_time: Date
  public name: string
  public parent_task_run_id: string
  public state_id: string
  public state_type: State
  public state: StateObj
  public tags: string[]
  public task_run_count: number
  public updated: Date

  constructor(flow: IFlowRun) {
    this.id = flow.id
    this.deployment_id = flow.deployment_id
    this.flow_id = flow.flow_id
    this.flow_version = flow.flow_version
    this.idempotency_key = flow.idempotency_key
    this.next_scheduled_start_time = flow.next_scheduled_start_time
    this.parameters = flow.parameters
    this.auto_scheduled = flow.auto_scheduled
    this.context = flow.context
    this.emperical_config = flow.emperical_config
    this.emperical_policy = flow.emperical_policy
    this.estimated_run_time = flow.estimated_run_time
    this.estimated_start_time_delta = flow.estimated_start_time_delta
    this.total_run_time = flow.total_run_time
    this.start_time = flow.start_time
    this.end_time = flow.end_time
    this.name = flow.name
    this.parent_task_run_id = flow.parent_task_run_id
    this.state_id = flow.state_id
    this.state_type = flow.state_type
    this.state = flow.state
    this.tags = flow.tags
    this.task_run_count = flow.task_run_count
    this.updated = flow.updated
  }
}
