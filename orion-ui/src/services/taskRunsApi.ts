import { TaskRunsApi as OrionDesignTaskRunsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionTaskRunsApi extends ApiRoute(OrionDesignTaskRunsApi) {}

export const taskRunsApi = createActions(new OrionTaskRunsApi())