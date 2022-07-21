import { NotificationsApi as OrionDesignNotificationsApi } from '@prefecthq/orion-design'
import { createActions } from '@prefecthq/vue-compositions'
import { ApiRoute } from '@/mixins/ApiRoute'

export class OrionNotificationsApi extends ApiRoute(OrionDesignNotificationsApi) {}

export const notificationsApi = createActions(new OrionNotificationsApi())