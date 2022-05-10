import { SearchApi as OrionDesignSearchApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionSearchApi extends ApiRoute(OrionDesignSearchApi) {}

export const searchApi = createActions(new OrionSearchApi())