export interface ILog {
  id: string,
  created: Date,
  updated: Date,
  name: string,
  level: number,
  message: string,
  timestamp: Date,
  flowRunId: string,
  taskRunId: string,
}

export class Log implements ILog {
  public readonly id: string
  public readonly created: Date
  public readonly updated: Date
  public name: string
  public level: number
  public message: string
  public timestamp: Date
  public flowRunId: string
  public taskRunId: string

  public constructor(log: ILog) {
    this.id = log.id
    this.created = log.created
    this.updated = log.updated
    this.name = log.name
    this.level = log.level
    this.message = log.message
    this.timestamp = log.timestamp
    this.flowRunId = log.flowRunId
    this.taskRunId = log.taskRunId
  }
}
