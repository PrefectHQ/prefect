import { BlockDocumentsApi as OrionDesignBlockDocumentsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionBlockDocumentsApi extends ApiRoute(OrionDesignBlockDocumentsApi) {}

export const blockDocumentsApi = createActions(new OrionBlockDocumentsApi())