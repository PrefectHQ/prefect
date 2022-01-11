import { AxiosResponse } from 'axios'
import { LogsRequestFilter } from '..'
import { Log } from '../models/Log'
import { Api } from './Api'

export type ILogResponse = {
  id: string,
  created: string,
  updated: string,
  name: string,
  level: number,
  message: string,
  timestamp: string,
  flow_run_id: string,
  task_run_id: string,
}

export class LogsApi extends Api {
  public constructor() {
    super('/api/logs')
  }

  public filter(filter?: LogsRequestFilter): Promise<Log[]> {
    return this.post('/filter', filter).then(response => this.logsResponseMapper(response))
  }

  protected logMapper(log: ILogResponse): Log {
    return new Log({
      id: log.id,
      created: new Date(log.created),
      updated: new Date(log.updated),
      name: log.name,
      level: log.level,
      message: log.message,
      timestamp: new Date(log.timestamp),
      flowRunId: log.flow_run_id,
      taskRunId: log.task_run_id,
    })
  }

  protected logsResponseMapper({ data }: AxiosResponse<ILogResponse[]>): Log[] {
    return data.map(log => this.logMapper(log))
  }
}

export const Logs = new LogsApi()
