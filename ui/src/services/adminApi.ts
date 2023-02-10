import { AdminApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionAdminApi extends ApiRoute(AdminApi) {}

export const adminApi = createActions(new OrionAdminApi())