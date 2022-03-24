import { createActions } from '@prefecthq/vue-compositions'
import { ILogResponse } from '@/models/ILogResponse'
import { Log } from '@/models/Log'
import { Api, Route } from '@/services/Api'
import { translate } from '@/services/Translate'
import { LogsRequestFilter } from '@/types/LogsRequestFilter'

export class LogsApi extends Api {

  protected route: Route = '/logs'

  public getLogs(filter?: LogsRequestFilter): Promise<Log[]> {
    return this.post<ILogResponse[]>('/filter', filter)
      .then(({ data }) => data.map(x => translate.toDestination('ILogResponse:Log', x)))
  }

}

export const logsApi = createActions(new LogsApi())
