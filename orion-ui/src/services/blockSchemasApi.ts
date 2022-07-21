import { BlockSchemasApi as OrionDesignBlockSchemasApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionBlockSchemasApi extends ApiRoute(OrionDesignBlockSchemasApi) {}

export const blockSchemasApi = createActions(new OrionBlockSchemasApi())