import { UseSubscription } from '@prefecthq/vue-compositions/src/subscribe/types'
import { InjectionKey } from 'vue'
import { DeploymentsApi } from '@/services/DeploymentsApi'
import { FlowsApi } from '@/services/FlowsApi'
import { WorkQueuesApi } from '@/services/WorkQueuesApi'


export type WorkQueueSubscription = UseSubscription<WorkQueuesApi['getWorkQueue']>
export type WorkQueuesListSubscription = UseSubscription<WorkQueuesApi['getWorkQueues']>
export type FlowsListSubscription = UseSubscription<FlowsApi['getFlows']>
export type DeploymentsListSubscription = UseSubscription<DeploymentsApi['getDeployments']>


export const workQueueSubscriptionKey: InjectionKey<WorkQueueSubscription> = Symbol('workQueueSubscriptionKey')
export const workQueuesListSubscriptionKey: InjectionKey<WorkQueuesListSubscription> = Symbol('workQueuesListSubscriptionKey')
export const flowsListSubscriptionKey: InjectionKey<FlowsListSubscription> = Symbol('flowsListSubscriptionKey')
export const deploymentsListSubscriptionKey: InjectionKey<DeploymentsListSubscription> = Symbol('deploymentsListSubscriptionKey')
