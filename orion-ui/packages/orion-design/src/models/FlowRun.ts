import { IState } from '@/models/State'
import { StateType } from '@/models/StateType'

export interface IFlowRun {
  id: string,
  flowId: string,
  deploymentId: string | null,
  flowVersion: string | null,
  idempotencyKey: string | null,
  expectedStartTime: string | null,
  nextScheduledStartTime: string | null,
  parameters: unknown,
  autoScheduled: boolean | null,
  context: unknown,
  empiricalConfig: unknown,
  empiricalPolicy: unknown,
  estimatedRunTime: number | null,
  estimatedStartTimeDelta: number | null,
  totalRunTime: number | null,
  startTime: Date | null,
  endTime: Date | null,
  name: string | null,
  parentTaskRunId: string | null,
  stateId: string | null,
  stateType: StateType | null,
  state: IState | null,
  tags: string[] | null,
  runCount: number | null,
  created: Date,
  updated: Date,
}

export class FlowRun implements IFlowRun {
  public readonly id: string
  public readonly flowId: string
  public readonly deploymentId: string | null
  public flowVersion: string | null
  public idempotencyKey: string | null
  public expectedStartTime: string | null
  public nextScheduledStartTime: string | null
  public parameters: unknown
  public autoScheduled: boolean | null
  public context: unknown
  public empiricalConfig: unknown
  public empiricalPolicy: unknown
  public estimatedRunTime: number | null
  public estimatedStartTimeDelta: number | null
  public totalRunTime: number | null
  public startTime: Date | null
  public endTime: Date | null
  public name: string | null
  public parentTaskRunId: string | null
  public stateId: string | null
  public stateType: StateType | null
  public state: IState | null
  public tags: string[] | null
  public runCount: number | null
  public created: Date
  public updated: Date

  public constructor(flow: IFlowRun) {
    this.id = flow.id
    this.deploymentId = flow.deploymentId
    this.flowId = flow.flowId
    this.flowVersion = flow.flowVersion
    this.idempotencyKey = flow.idempotencyKey
    this.expectedStartTime = flow.expectedStartTime
    this.nextScheduledStartTime = flow.nextScheduledStartTime
    this.parameters = flow.parameters
    this.autoScheduled = flow.autoScheduled
    this.context = flow.context
    this.empiricalConfig = flow.empiricalConfig
    this.empiricalPolicy = flow.empiricalPolicy
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
    this.runCount = flow.runCount
    this.created = flow.created
    this.updated = flow.updated
  }

  public get duration(): number {
    return this.totalRunTime ?? this.estimatedRunTime ?? 0
  }
}
