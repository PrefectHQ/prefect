import { IState } from "./State"
import { StateType } from "./StateType"

export interface IFlowRun {
  id: string
  deploymentId: string
  flowId: string
  flowVersion: string
  idempotencyKey: string | null
  nextScheduledStartTime: string | null
  parameters: unknown
  autoScheduled: boolean
  context: unknown
  empericalConfig: unknown
  empericalPolicy: unknown
  estimatedRunTime: number
  estimatedStartTimeDelta: number
  totalRunTime: number
  startTime: Date
  endTime: Date
  name: string
  parentTaskRunId: string
  stateId: string
  stateType: StateType
  state: IState
  tags: string[]
  taskRunCount: number
  updated: Date
}

export class FlowRun implements IFlowRun {
  public readonly id: string
  public readonly deploymentId: string
  public readonly flowId: string
  public flowVersion: string
  public idempotencyKey: string | null
  public nextScheduledStartTime: string | null
  public parameters: unknown
  public autoScheduled: boolean
  public context: unknown
  public empericalConfig: unknown
  public empericalPolicy: unknown
  public estimatedRunTime: number
  public estimatedStartTimeDelta: number
  public totalRunTime: number
  public startTime: Date
  public endTime: Date
  public name: string
  public parentTaskRunId: string
  public stateId: string
  public stateType: StateType
  public state: IState
  public tags: string[]
  public taskRunCount: number
  public updated: Date

  constructor(flow: IFlowRun) {
    this.id = flow.id
    this.deploymentId = flow.deploymentId
    this.flowId = flow.flowId
    this.flowVersion = flow.flowVersion
    this.idempotencyKey = flow.idempotencyKey
    this.nextScheduledStartTime = flow.nextScheduledStartTime
    this.parameters = flow.parameters
    this.autoScheduled = flow.autoScheduled
    this.context = flow.context
    this.empericalConfig = flow.empericalConfig
    this.empericalPolicy = flow.empericalPolicy
    this.estimatedRunTime = flow.estimatedRunTime
    this.estimatedStartTimeDelta = flow.estimatedStartTimeDelta
    this.totalRunTime = flow.totalRunTime
    this.startTime = flow.startTime
    this.endTime = flow.endTime
    this.name = flow.name
    this.parentTaskRunId = flow.parentTaskRunId
    this.stateId = flow.stateId
    this.stateType = flow.stateType
    this.state = flow.state
    this.tags = flow.tags
    this.taskRunCount = flow.taskRunCount
    this.updated = flow.updated
  }
}
