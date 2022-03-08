import { showPanel, closePanel, exitPanel, showToast } from '@prefecthq/miter-design'
import { inject } from 'vue'
import { createDeploymentFlowRunKey, DeploymentsApi, deploymentsApi, getDeploymentsCountKey, getDeploymentsKey } from '@/services/DeploymentsApi'
import { FlowRunsApi, flowRunsApi, getFlowRunsCountKey } from '@/services/FlowRunsApi'
import { workQueuesApi, getWorkQueueKey, pauseWorkQueueKey, resumeWorkQueueKey, createWorkQueueKey, updateWorkQueueKey, deleteWorkQueueKey, WorkQueuesApi } from '@/services/WorkQueuesApi'
import { showPanelKey, closePanelKey, exitPanelKey, ShowPanel, ClosePanel, ExitPanel } from '@/utilities/panels'
import { WorkQueuesListSubscription, workQueuesListSubscriptionKey } from '@/utilities/subscriptions'
import { showToastKey, ShowToast } from '@/utilities/toasts'

export type InjectedServices = {
  useShowPanel: ShowPanel,
  useClosePanel: ClosePanel,
  useExitPanel: ExitPanel,
  useShowToast: ShowToast,
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
  const getDeploymentsCount = inject(getDeploymentsCountKey, deploymentsApi.getDeploymentsCount)
  const createDeploymentFlowRun = inject(createDeploymentFlowRunKey, deploymentsApi.createDeploymentFlowRun)
  const getFlowRunsCount = inject(getFlowRunsCountKey, flowRunsApi.getFlowRunsCount)

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
    getDeploymentsCount,
    createDeploymentFlowRun,
    getFlowRunsCount,
  }
}