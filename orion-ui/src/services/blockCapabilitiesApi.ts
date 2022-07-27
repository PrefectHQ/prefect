import { BlockCapabilitiesApi as OrionDesignBlockCapabilitiesApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionBlockCapabilitiesApi extends ApiRoute(OrionDesignBlockCapabilitiesApi) {}

export const blockCapabilitiesApi = createActions(new OrionBlockCapabilitiesApi())