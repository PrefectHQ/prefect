import { createActions } from '@prefecthq/vue-compositions'
import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import {
  Deployment,
  IFlowDataResponse,
  FlowData,
  FlowRunner,
  IFlowRunnerResponse,
  IScheduleResponse,
  Schedule,
  isRRuleScheduleResponse,
  isCronScheduleResponse,
  isIntervalScheduleResponse,
  RRuleSchedule,
  CronSchedule,
  IntervalSchedule,
  StateType,
  Flow
} from '@/models'
import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { IFlowResponse } from '@/services/FlowsApi'
import { DateString } from '@/types/dates'

export type IDeploymentResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string,
  flow_id: string,
  flow_data: IFlowDataResponse,
  schedule: IScheduleResponse | null,
  is_schedule_active: boolean | null,
  parameters: Record<string, string>,
  tags: string[] | null,
  flow_runner: IFlowRunnerResponse,
}

// this type is incomplete
// https://orion-docs.prefect.io/api-ref/rest-api/#/Deployments/create_flow_run_from_deployment_deployments__id__create_flow_run_post
export type ICreateFlowRunRequest = {
  state: {
    type: StateType,
    message: string,
  },
}

export class DeploymentsApi extends Api {

  protected route: Route = '/deployments'

  public getDeployment(deploymentId: string): Promise<Deployment> {
    return this.get<IDeploymentResponse>(`/${deploymentId}`).then(response => this.mapDeploymentResponse(response))
  }

  public getDeployments(filter: UnionFilters): Promise<Deployment[]> {
    return this.post<IDeploymentResponse[]>('/filter', filter).then(response => this.mapDeploymentsResponse(response))
  }

  public getDeploymentsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  public createDeploymentFlowRun(deploymentId: string, body: ICreateFlowRunRequest): Promise<Flow> {
    return this.post<IFlowResponse>(`/${deploymentId}/create_flow_run`, body).then(response => this.mapFlowResponse(response))
  }

  protected mapDeployments(data: IDeploymentResponse): Deployment {
    return new Deployment({
      id: data.id,
      created: new Date(data.created),
      updated: new Date(data.updated),
      name: data.name,
      flowId: data.flow_id,
      flowData: this.mapFlowData(data.flow_data),
      schedule: data.schedule ? this.mapSchedule(data.schedule) : null,
      isScheduleActive: data.is_schedule_active,
      parameters: data.parameters,
      tags: data.tags,
      flowRunner: this.mapFlowRunner(data.flow_runner),
    })
  }

  protected mapFlowData(data: IFlowDataResponse): FlowData {
    return new FlowData({
      encoding: data.encoding,
      blob: data.blob,
    })
  }

  protected mapFlowRunner(data: IFlowRunnerResponse): FlowRunner {
    return new FlowRunner({
      type: data.type,
      config: data.config,
    })
  }

  protected mapSchedule(data: IScheduleResponse): Schedule {
    if (isRRuleScheduleResponse(data)) {
      return new RRuleSchedule({
        timezone: data.timezone,
        rrule: data.rrule,
      })
    }

    if (isCronScheduleResponse(data)) {
      return new CronSchedule({
        timezone: data.timezone,
        cron: data.cron,
        dayOr: data.day_or,
      })
    }

    if (isIntervalScheduleResponse(data)) {
      return new IntervalSchedule({
        timezone: data.timezone,
        interval: data.interval,
        anchorDate: data.anchor_date,
      })
    }

    throw 'Invalid IScheduleResponse'
  }

  protected mapDeploymentsResponse({ data }: AxiosResponse<IDeploymentResponse[]>): Deployment[] {
    return data.map(x => this.mapDeployments(x))
  }

  protected mapDeploymentResponse({ data }: AxiosResponse<IDeploymentResponse>): Deployment {
    return this.mapDeployments(data)
  }

  protected mapFlow(data: IFlowResponse): Flow {
    return new Flow({
      id: data.id,
      name: data.name,
      tags: data.tags,
      created: new Date(data.created),
      updated: new Date(data.updated),
    })
  }

  protected mapFlowResponse({ data }: AxiosResponse<IFlowResponse>): Flow {
    return this.mapFlow(data)
  }

  protected mapFlowsResponse({ data }: AxiosResponse<IFlowResponse[]>): Flow[] {
    return data.map(x => this.mapFlow(x))
  }

}

export const deploymentsApi = createActions(new DeploymentsApi())

export const getDeploymentsKey: InjectionKey<DeploymentsApi['getDeployments']> = Symbol()
export const getDeploymentsCountKey: InjectionKey<DeploymentsApi['getDeploymentsCount']> = Symbol()
export const createDeploymentFlowRunKey: InjectionKey<DeploymentsApi['createDeploymentFlowRun']> = Symbol()