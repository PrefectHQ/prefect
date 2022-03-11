import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
import {FlowsApi} from '@/services/FlowsApi'
import { InjectionKey } from 'vue'
import { WorkQueuesApi } from '@/services/WorkQueuesApi'


export type WorkQueueSubscription = Subscription<WorkQueuesApi['getWorkQueue']>
export type WorkQueuesListSubscription = Subscription<WorkQueuesApi['getWorkQueues']>


export const workQueueSubscriptionKey: InjectionKey<WorkQueueSubscription> = Symbol()
export const workQueuesListSubscriptionKey: InjectionKey<WorkQueuesListSubscription> = Symbol()
