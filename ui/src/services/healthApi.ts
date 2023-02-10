import { HealthApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionHealthApi extends ApiRoute(HealthApi) {}

export const healthApi = createActions(new OrionHealthApi())