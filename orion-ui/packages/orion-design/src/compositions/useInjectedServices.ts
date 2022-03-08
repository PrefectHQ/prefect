import { FlowRunsApi, flowRunsApi, getFlowRunsCountKey } from '@/services/FlowRunsApi'
import { inject } from 'vue'
import { createDeploymentFlowRunKey, DeploymentsApi, deploymentsApi, getDeploymentsCountKey, getDeploymentsKey } from '@/services/DeploymentsApi'
import { workQueuesApi, getWorkQueueKey, pauseWorkQueueKey, resumeWorkQueueKey, createWorkQueueKey, updateWorkQueueKey, deleteWorkQueueKey, WorkQueuesApi } from '@/services/WorkQueuesApi'
import { WorkQueuesListSubscription, workQueuesListSubscriptionKey } from '@/utilities/subscriptions'

export type InjectedServices = {
  workQueuesListSubscription: WorkQueuesListSubscription,
  getWorkQueue: WorkQueuesApi['getWorkQueue'],
  createWorkQueue: WorkQueuesApi['createWorkQueue'],
  pauseWorkQueue: WorkQueuesApi['pauseWorkQueue'],
  resumeWorkQueue: WorkQueuesApi['resumeWorkQueue'],
  updateWorkQueue: WorkQueuesApi['updateWorkQueue'],
  deleteWorkQueue: WorkQueuesApi['deleteWorkQueue'],
  getDeployments: DeploymentsApi['getDeployments'],
  getDeploymentsCount: DeploymentsApi['getDeploymentsCount'],
  createDeploymentFlowRun: DeploymentsApi['createDeploymentFlowRun'],
  getFlowRunsCount: FlowRunsApi['getFlowRunsCount'],
}

export function useInjectedServices(): InjectedServices {
  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey, null)!
  const getWorkQueue = inject(getWorkQueueKey, workQueuesApi.getWorkQueue)
  const createWorkQueue = inject(createWorkQueueKey, workQueuesApi.createWorkQueue)
  const pauseWorkQueue = inject(pauseWorkQueueKey, workQueuesApi.pauseWorkQueue)
  const resumeWorkQueue = inject(resumeWorkQueueKey, workQueuesApi.resumeWorkQueue)
  const updateWorkQueue = inject(updateWorkQueueKey, workQueuesApi.updateWorkQueue)
  const deleteWorkQueue = inject(deleteWorkQueueKey, workQueuesApi.deleteWorkQueue)
  const getDeployments = inject(getDeploymentsKey, deploymentsApi.getDeployments)
  const getDeploymentsCount = inject(getDeploymentsCountKey, deploymentsApi.getDeploymentsCount)
  const createDeploymentFlowRun = inject(createDeploymentFlowRunKey, deploymentsApi.createDeploymentFlowRun)
  const getFlowRunsCount = inject(getFlowRunsCountKey, flowRunsApi.getFlowRunsCount)

  return {
    workQueuesListSubscription,
    getWorkQueue,
    createWorkQueue,
    pauseWorkQueue,
    resumeWorkQueue,
    updateWorkQueue,
    deleteWorkQueue,
    getDeployments,
    getDeploymentsCount,
    createDeploymentFlowRun,
    getFlowRunsCount,
  }
}