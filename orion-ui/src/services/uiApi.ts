import { UiApi as OrionDesignUiApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionUiApi extends ApiRoute(OrionDesignUiApi) {}

export const UiApi = createActions(new OrionUiApi())