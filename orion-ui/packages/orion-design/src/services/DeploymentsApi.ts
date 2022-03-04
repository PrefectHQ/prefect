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
  IntervalSchedule
} from '@/models'
import { Api, Route } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'
import { DateString } from '@/types/dates'

export type IDeploymentResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string,
  flow_id: string,
  flow_data: IFlowDataResponse,
  schedule: IScheduleResponse,
  is_schedule_active: boolean | null,
  parameters: unknown,
  tags: string[] | null,
  flow_runner: IFlowRunnerResponse,
}

export class DeploymentsApi extends Api {

  protected route: Route = '/deployments'

  public getDeployment(id: string): Promise<Deployment> {
    return this.get<IDeploymentResponse>(`/${id}`).then(response => this.mapDeploymentResponse(response))
  }

  public getDeployments(filter: UnionFilters): Promise<Deployment[]> {
    return this.post<IDeploymentResponse[]>('/filter', filter).then(response => this.mapDeploymentsResponse(response))
  }

  public getDeploymentsCount(filter: UnionFilters): Promise<number> {
    return this.post<number>('/count', filter).then(({ data }) => data)
  }

  protected mapDeployments(data: IDeploymentResponse): Deployment {
    return new Deployment({
      id: data.id,
      created: new Date(data.created),
      updated: new Date(data.updated),
      name: data.name,
      flowId: data.flow_id,
      flowData: this.mapFlowData(data.flow_data),
      schedule: this.mapSchedule(data.schedule),
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

}

export const deploymentsApi = createActions(new DeploymentsApi())

export const getDeploymentsCountKey: InjectionKey<DeploymentsApi['getDeploymentsCount']> = Symbol()