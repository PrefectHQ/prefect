import { FlowsApi as OrionDesignFlowsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionFlowsApi extends ApiRoute(OrionDesignFlowsApi) {}

export const flowsApi = createActions(new OrionFlowsApi())