import { FlowRunsApi as OrionDesignFlowRunsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionFlowRunsApi extends ApiRoute(OrionDesignFlowRunsApi) {}

export const flowRunsApi = createActions(new OrionFlowRunsApi())