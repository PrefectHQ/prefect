import { HealthApi } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class ServerHealthApi extends ApiRoute(HealthApi) {}

export const healthApi = createActions(new ServerHealthApi())