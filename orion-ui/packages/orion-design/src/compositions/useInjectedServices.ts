import { showPanel, closePanel, exitPanel, showToast } from '@prefecthq/miter-design'
import { inject } from 'vue'
import { Deployment } from '@/models/Deployment'
import { WorkQueue } from '@/models/WorkQueue'
import { deploymentsApi, getDeploymentsKey } from '@/services/DeploymentsApi'
import { UnionFilters } from '@/services/Filter'
import { workQueuesApi, getWorkQueueKey, pauseWorkQueueKey, resumeWorkQueueKey, createWorkQueueKey, updateWorkQueueKey, deleteWorkQueueKey, IWorkQueueRequest } from '@/services/WorkQueuesApi'
import { showPanelKey, closePanelKey, exitPanelKey, refreshWorkQueuesListKey, ShowPanel, ClosePanel, ExitPanel } from '@/utilities/panels'
import { showToastKey, ShowToast } from '@/utilities/toasts'

export type InjectedServices = {
  useShowPanel: ShowPanel,
  useClosePanel: ClosePanel,
  useExitPanel: ExitPanel,
  useShowToast: ShowToast,
  refreshWorkQueuesList: () => Promise<void>,
  getWorkQueue: (workQueueId: string) => Promise<WorkQueue>,
  createWorkQueue: (request: IWorkQueueRequest) => Promise<WorkQueue>,
  pauseWorkQueue: (workQueueId: string) => Promise<void>,
  resumeWorkQueue: (workQueueId: string) => Promise<void>,
  updateWorkQueue: (workQueueId: string, request: IWorkQueueRequest) => Promise<void>,
  deleteWorkQueue: (workQueueId: string) => Promise<void>,
  getDeployments: (filter: UnionFilters) => Promise<Deployment[]>,
}

// this is only used to ensure callable type for "refresh" method if actual refresh is not provided
// eslint-disable-next-line @typescript-eslint/no-empty-function
async function emptyRefresh(): Promise<void> {}

export function useInjectedServices(): InjectedServices {
  const useShowPanel = inject(showPanelKey, showPanel)
  const useClosePanel = inject(closePanelKey, closePanel)
  const useExitPanel = inject(exitPanelKey, exitPanel)
  const useShowToast = inject(showToastKey, showToast)
  const refreshWorkQueuesList = inject(refreshWorkQueuesListKey) ?? emptyRefresh
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
    refreshWorkQueuesList,
    getWorkQueue,
    createWorkQueue,
    pauseWorkQueue,
    resumeWorkQueue,
    updateWorkQueue,
    deleteWorkQueue,
    getDeployments,
  }
}