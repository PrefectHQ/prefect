import { DeploymentsApi as OrionDesignDeploymentsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionDeploymentsApi extends ApiRoute(OrionDesignDeploymentsApi) {}

export const deploymentsApi = createActions(new OrionDeploymentsApi())