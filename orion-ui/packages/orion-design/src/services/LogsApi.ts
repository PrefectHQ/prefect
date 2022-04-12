import { InjectionKey } from 'vue'
import { ApiRoute } from '.'
import { ILogResponse } from '@/models/ILogResponse'
import { Log } from '@/models/Log'
import { Api } from '@/services/Api'
import { mapper } from '@/services/Mapper'
import { LogsRequestFilter } from '@/types/LogsRequestFilter'

export class LogsApi extends Api {

  protected route: ApiRoute = '/logs'

  public getLogs(filter?: LogsRequestFilter): Promise<Log[]> {
    return this.post<ILogResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('ILogResponse', data, 'Log'))
  }

}

export const logsApiKey: InjectionKey<LogsApi> = Symbol('logsApiKey')
