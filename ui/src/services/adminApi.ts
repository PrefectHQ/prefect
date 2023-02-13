import { AdminApi } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class ServerAdminApi extends ApiRoute(AdminApi) {}

export const adminApi = createActions(new ServerAdminApi())