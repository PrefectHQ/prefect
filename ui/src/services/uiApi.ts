import { UiApi as OrionDesignUiApi } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionUiApi extends ApiRoute(OrionDesignUiApi) {}

export const uiApi = createActions(new OrionUiApi())