import { showPanel, closePanel, exitPanel, showToast } from '@prefecthq/miter-design'
import { inject } from 'vue'
import { Deployment } from '@/models/Deployment'
import { WorkQueue } from '@/models/WorkQueue'
import { deploymentsApi, getDeploymentsKey } from '@/services/DeploymentsApi'
import { UnionFilters } from '@/services/Filter'
import { workQueuesApi, getWorkQueueKey, pauseWorkQueueKey, resumeWorkQueueKey, createWorkQueueKey, updateWorkQueueKey, deleteWorkQueueKey, IWorkQueueRequest } from '@/services/WorkQueuesApi'
import { showPanelKey, closePanelKey, exitPanelKey, ShowPanel, ClosePanel, ExitPanel } from '@/utilities/panels'
import { WorkQueuesListSubscription, workQueuesListSubscriptionKey } from '@/utilities/subscriptions'
import { showToastKey, ShowToast } from '@/utilities/toasts'

export type InjectedServices = {
  useShowPanel: ShowPanel,
  useClosePanel: ClosePanel,
  useExitPanel: ExitPanel,
  useShowToast: ShowToast,
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
  const useShowPanel = inject(showPanelKey, showPanel)
  const useClosePanel = inject(closePanelKey, closePanel)
  const useExitPanel = inject(exitPanelKey, exitPanel)
  const useShowToast = inject(showToastKey, showToast)
  const workQueuesListSubscription = inject(workQueuesListSubscriptionKey)!
  const getWorkQueue = inject(getWorkQueueKey, workQueuesApi.getWorkQueue)
  const createWorkQueue = inject(createWorkQueueKey, workQueuesApi.createWorkQueue)
  const pauseWorkQueue = inject(pauseWorkQueueKey, workQueuesApi.pauseWorkQueue)
  const resumeWorkQueue = inject(resumeWorkQueueKey, workQueuesApi.resumeWorkQueue)
  const updateWorkQueue = inject(updateWorkQueueKey, workQueuesApi.updateWorkQueue)
  const deleteWorkQueue = inject(deleteWorkQueueKey, workQueuesApi.deleteWorkQueue)
  const getDeployments = inject(getDeploymentsKey, deploymentsApi.getDeployments)

  return {
    useShowPanel,
    useClosePanel,
    useExitPanel,
    useShowToast,
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