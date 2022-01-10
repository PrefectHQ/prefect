import { StateType } from '../types/StateType'
import { State } from './State'

export interface ITaskRun {
  id: string,
  flowRunId: string,
  cacheExpiration: string,
  cacheKey: string,
  created: Date,
  dynamicKey: string,
  empiricalPolicy: Record<string, any>,
  estimatedRunTime: number,
  estimatedStartTimeDelta: number,
  totalRunTime: number,
  expectedStartTime: Date,
  nextScheduledStartTime: string | null,
  runCount: number,
  name: string,
  taskInputs: Record<string, any>,
  taskKey: string,
  taskVersion: string,
  updated: Date,
  startTime: Date,
  endTime: Date,
  stateId: string,
  stateType: StateType,
  state: State,
  duration: number,
  subflowRuns: boolean,
  tags: string[],
}

export class TaskRun implements ITaskRun {
  public id: string
  public flowRunId: string
  public cacheExpiration: string
  public cacheKey: string
  public created: Date
  public dynamicKey: string
  public empiricalPolicy: Record<string, any>
  public estimatedRunTime: number
  public estimatedStartTimeDelta: number
  public totalRunTime: number
  public expectedStartTime: Date
  public nextScheduledStartTime: string | null
  public runCount: number
  public name: string
  public taskInputs: Record<string, any>
  public taskKey: string
  public taskVersion: string
  public updated: Date
  public startTime: Date
  public endTime: Date
  public stateId: string
  public stateType: StateType
  public state: State
  public duration: number
  public subflowRuns: boolean
  public tags: string[]

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
    this.duration = taskRun.duration
    this.subflowRuns = taskRun.subflowRuns
    this.tags = taskRun.tags
  }
}