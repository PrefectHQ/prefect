import { BlockTypesApi as OrionDesignBlockTypesApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionBlockTypesApi extends ApiRoute(OrionDesignBlockTypesApi) {}

export const blockTypesApi = createActions(new OrionBlockTypesApi())