import { createActions } from '@prefecthq/vue-compositions'
import { InjectionKey } from 'vue'
import { Deployment } from '@/models/Deployment'
import { Flow } from '@/models/Flow'
import { ICreateFlowRunRequest } from '@/models/ICreateFlowRunRequest'
import { IDeploymentResponse } from '@/models/IDeploymentResponse'
import { IFlowResponse } from '@/models/IFlowResponse'
import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { translate } from '@/services/Translate'

export class DeploymentsApi extends Api {

  protected route: Route = '/deployments'

  public getDeployment(deploymentId: string): Promise<Deployment> {
    return this.get<IDeploymentResponse>(`/${deploymentId}`)
      .then(({ data }) => translate.toDestination('IDeploymentResponse:Deployment', data))
  }

  public getDeployments(filter: UnionFilters): Promise<Deployment[]> {
    return this.post<IDeploymentResponse[]>('/filter', filter)
      .then(({ data }) => data.map(x => translate.toDestination('IDeploymentResponse:Deployment', x)))
  }

  public getDeploymentsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public createDeploymentFlowRun(deploymentId: string, body: ICreateFlowRunRequest): Promise<Flow> {
    return this.post<IFlowResponse>(`/${deploymentId}/create_flow_run`, body)
      .then(({ data }) => translate.toDestination('IFlowResponse:Flow', data))
  }

  public deleteDeployment(deploymentId: string): Promise<void> {
    return this.delete(`/${deploymentId}`)
  }
}

export const deploymentsApi = createActions(new DeploymentsApi())

export const getDeploymentsCountKey: InjectionKey<DeploymentsApi['getDeploymentsCount']> = Symbol()
export const getDeploymentsKey: InjectionKey<DeploymentsApi['getDeployments']> = Symbol()
export const createDeploymentFlowRunKey: InjectionKey<DeploymentsApi['createDeploymentFlowRun']> = Symbol()
export const deleteDeploymentKey: InjectionKey<DeploymentsApi['deleteDeployment']> = Symbol()
