import { InjectionKey } from 'vue'
import { Deployment } from '@/models/Deployment'
import { Flow } from '@/models/Flow'
import { ICreateFlowRunRequest } from '@/models/ICreateFlowRunRequest'
import { IDeploymentResponse } from '@/models/IDeploymentResponse'
import { IFlowResponse } from '@/models/IFlowResponse'
import { Api, ApiRoute } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { mapper } from '@/services/Mapper'

export class DeploymentsApi extends Api {

  protected override route: ApiRoute = '/deployments'

  public getDeployment(deploymentId: string): Promise<Deployment> {
    return this.get<IDeploymentResponse>(`/${deploymentId}`)
      .then(({ data }) => mapper.map('IDeploymentResponse', data, 'Deployment'))
  }

  public getDeployments(filter: UnionFilters): Promise<Deployment[]> {
    return this.post<IDeploymentResponse[]>('/filter', filter)
      .then(({ data }) => mapper.map('IDeploymentResponse', data, 'Deployment'))
  }

  public getDeploymentsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public createDeploymentFlowRun(deploymentId: string, body: ICreateFlowRunRequest): Promise<Flow> {
    return this.post<IFlowResponse>(`/${deploymentId}/create_flow_run`, body)
      .then(({ data }) => mapper.map('IFlowResponse', data, 'Flow'))
  }

  public deleteDeployment(deploymentId: string): Promise<void> {
    return this.delete(`/${deploymentId}`)
  }
}

export const deploymentsApiKey: InjectionKey<DeploymentsApi> = Symbol('deploymentsApiKey')
