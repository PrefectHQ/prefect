import { inject } from 'vue'
import { DeploymentsApi, deploymentsApiKey } from '@/services/DeploymentsApi'
import { FlowRunsApi, flowRunsApiKey } from '@/services/FlowRunsApi'
import { WorkQueuesApi, workQueuesApiKey } from '@/services/WorkQueuesApi'
import { requiredInject } from '@/utilities/inject'
import { WorkQueuesListSubscription, workQueuesListSubscriptionKey } from '@/utilities/subscriptions'


export type InjectedServices = {
  workQueuesListSubscription: WorkQueuesListSubscription,
  workQueuesApi: WorkQueuesApi,
  deploymentsApi: DeploymentsApi,
  flowRunsApi: FlowRunsApi,
}

export function useInjectedServices(): InjectedServices {
  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey, null)!
  const workQueuesApi = requiredInject(workQueuesApiKey)
  const deploymentsApi = requiredInject(deploymentsApiKey)
  const flowRunsApi = requiredInject(flowRunsApiKey)

  return {
    workQueuesListSubscription,
    workQueuesApi,
    deploymentsApi,
    flowRunsApi,
  }
}