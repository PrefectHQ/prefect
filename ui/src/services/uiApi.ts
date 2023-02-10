import { UiApi as PrefectUiLibraryApi } from '@prefecthq/prefect-ui-library'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class UiApi extends ApiRoute(PrefectUiLibraryApi) {}

export const uiApi = createActions(new UiApi())