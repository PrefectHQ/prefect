import { UseSubscription } from '@prefecthq/vue-compositions/src/subscribe/types'
import { InjectionKey } from 'vue'
import { WorkQueuesApi } from '@/services/WorkQueuesApi'


export type WorkQueueSubscription = UseSubscription<WorkQueuesApi['getWorkQueue']>
export type WorkQueuesListSubscription = UseSubscription<WorkQueuesApi['getWorkQueues']>


export const workQueueSubscriptionKey: InjectionKey<WorkQueueSubscription> = Symbol()
export const workQueuesListSubscriptionKey: InjectionKey<WorkQueuesListSubscription> = Symbol()
