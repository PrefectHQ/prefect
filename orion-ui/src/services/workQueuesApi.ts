import { WorkQueuesApi as OrionDesignWorkQueuesApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionWorkQueuesApi extends ApiRoute(OrionDesignWorkQueuesApi) {}

export const workQueuesApi = createActions(new OrionWorkQueuesApi())