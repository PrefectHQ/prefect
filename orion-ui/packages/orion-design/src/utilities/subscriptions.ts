import Subscription from '@prefecthq/vue-compositions/src/subscribe/subscription'
import { InjectionKey } from 'vue'
import { WorkQueuesApi } from '@/services/WorkQueuesApi'
import { FlowsApi } from '..'

export type WorkQueueSubscription = Subscription<WorkQueuesApi['getWorkQueue']>
export type WorkQueuesListSubscription = Subscription<WorkQueuesApi['getWorkQueues']>
export type FlowsListSubscription = Subscription<FlowsApi['getFlows']>

export const workQueueSubscriptionKey: InjectionKey<WorkQueueSubscription> = Symbol()
export const workQueuesListSubscriptionKey: InjectionKey<WorkQueuesListSubscription> = Symbol()
export const flowsListSubscriptionKey: InjectionKey<FlowsListSubscription>=Symbol()