import { IEmpiricalPolicy } from '@/models/EmpiricalPolicy'
import { IState } from '@/models/State'
import { StateType } from '@/models/StateType'
import { TaskInput } from '@/models/TaskInput'

export interface ITaskRun {
  id: string,
  flowRunId: string,
  cacheExpiration: string | null,
  cacheKey: string | null,
  created: Date,
  dynamicKey: string,
  empiricalPolicy: IEmpiricalPolicy | null,
  estimatedRunTime: number | null,
  estimatedStartTimeDelta: number | null,
  totalRunTime: number | null,
  expectedStartTime: Date | null,
  nextScheduledStartTime: string | null,
  runCount: number | null,
  name: string | null,
  taskInputs: Record<string, TaskInput[]> | null,
  taskKey: string,
  taskVersion: string | null,
  updated: Date,
  startTime: Date | null,
  endTime: Date | null,
  stateId: string | null,
  stateType: StateType | null,
  state: IState | null,
  tags: string[] | null,
}

export class TaskRun implements ITaskRun {
  public readonly id: string
  public readonly flowRunId: string
  public cacheExpiration: string | null
  public cacheKey: string | null
  public created: Date
  public dynamicKey: string
  public empiricalPolicy: IEmpiricalPolicy | null
  public estimatedRunTime: number | null
  public estimatedStartTimeDelta: number | null
  public totalRunTime: number | null
  public expectedStartTime: Date | null
  public nextScheduledStartTime: string | null
  public runCount: number | null
  public name: string | null
  public taskInputs: Record<string, TaskInput[]> | null
  public taskKey: string
  public taskVersion: string | null
  public updated: Date
  public startTime: Date | null
  public endTime: Date | null
  public stateId: string | null
  public stateType: StateType | null
  public state: IState | null
  public tags: string[] | null

  public constructor(taskRun: ITaskRun) {
    this.id = taskRun.id
    this.flowRunId = taskRun.flowRunId
    this.cacheExpiration = taskRun.cacheExpiration
    this.cacheKey = taskRun.cacheKey
    this.created = taskRun.created
    this.dynamicKey = taskRun.dynamicKey
    this.empiricalPolicy = taskRun.empiricalPolicy
    this.estimatedRunTime = taskRun.estimatedRunTime
    this.estimatedStartTimeDelta = taskRun.estimatedStartTimeDelta
    this.totalRunTime = taskRun.totalRunTime
    this.expectedStartTime = taskRun.expectedStartTime
    this.nextScheduledStartTime = taskRun.nextScheduledStartTime
    this.runCount = taskRun.runCount
    this.name = taskRun.name
    this.taskInputs = taskRun.taskInputs
    this.taskKey = taskRun.taskKey
    this.taskVersion = taskRun.taskVersion
    this.updated = taskRun.updated
    this.startTime = taskRun.startTime
    this.endTime = taskRun.endTime
    this.stateId = taskRun.stateId
    this.stateType = taskRun.stateType
    this.state = taskRun.state
    this.tags = taskRun.tags
  }

  public get duration(): number {
    return this.totalRunTime ?? this.estimatedRunTime ?? 0
  }
}