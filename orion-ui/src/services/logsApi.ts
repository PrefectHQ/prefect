import { LogsApi as OrionDesignLogsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionLogsApi extends ApiRoute(OrionDesignLogsApi) {}

export const logsApi = createActions(new OrionLogsApi())