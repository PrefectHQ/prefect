import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { ApiRoute } from '.'
import { ILogResponse } from '@/models/ILogResponse'
import { Log } from '@/models/Log'
import { Api } from '@/services/Api'
import { LogsRequestFilter } from '@/types/LogsRequestFilter'

export class LogsApi extends Api {

  protected route: ApiRoute = '/logs'

  public getLogs(filter?: LogsRequestFilter): Promise<Log[]> {
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

export const logsApiKey: InjectionKey<LogsApi> = Symbol('logsApiKey')
