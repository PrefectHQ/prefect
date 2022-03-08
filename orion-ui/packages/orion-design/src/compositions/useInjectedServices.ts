import { inject } from 'vue'
import { Deployment } from '@/models/Deployment'
import { WorkQueue } from '@/models/WorkQueue'
import { deploymentsApi, getDeploymentsKey } from '@/services/DeploymentsApi'
import { UnionFilters } from '@/services/Filter'
import { workQueuesApi, getWorkQueueKey, pauseWorkQueueKey, resumeWorkQueueKey, createWorkQueueKey, updateWorkQueueKey, deleteWorkQueueKey, IWorkQueueRequest } from '@/services/WorkQueuesApi'
import { WorkQueuesListSubscription, workQueuesListSubscriptionKey } from '@/utilities/subscriptions'

export type InjectedServices = {
  workQueuesListSubscription: WorkQueuesListSubscription,
  getWorkQueue: (workQueueId: string) => Promise<WorkQueue>,
  createWorkQueue: (request: IWorkQueueRequest) => Promise<WorkQueue>,
  pauseWorkQueue: (workQueueId: string) => Promise<void>,
  resumeWorkQueue: (workQueueId: string) => Promise<void>,
  updateWorkQueue: (workQueueId: string, request: IWorkQueueRequest) => Promise<void>,
  deleteWorkQueue: (workQueueId: string) => Promise<void>,
  getDeployments: (filter: UnionFilters) => Promise<Deployment[]>,
}

export function useInjectedServices(): InjectedServices {
  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey)!
  const getWorkQueue = inject(getWorkQueueKey, workQueuesApi.getWorkQueue)
  const createWorkQueue = inject(createWorkQueueKey, workQueuesApi.createWorkQueue)
  const pauseWorkQueue = inject(pauseWorkQueueKey, workQueuesApi.pauseWorkQueue)
  const resumeWorkQueue = inject(resumeWorkQueueKey, workQueuesApi.resumeWorkQueue)
  const updateWorkQueue = inject(updateWorkQueueKey, workQueuesApi.updateWorkQueue)
  const deleteWorkQueue = inject(deleteWorkQueueKey, workQueuesApi.deleteWorkQueue)
  const getDeployments = inject(getDeploymentsKey, deploymentsApi.getDeployments)

  return {
    workQueuesListSubscription,
    getWorkQueue,
    createWorkQueue,
    pauseWorkQueue,
    resumeWorkQueue,
    updateWorkQueue,
    deleteWorkQueue,
    getDeployments,
  }
}