import { AxiosResponse } from 'axios'
import { Deployment, IFlowDataResponse, FlowData, FlowRunner, IFlowRunnerResponse, IScheduleResponse, Schedule } from '@/models'
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
    return new Schedule({
      timezone: data.timezone,
      rrule: data.rrule,
      cron: data.cron,
      dayOr: data.day_or,
      interval: data.interval,
      anchorDate: data.anchor_date,
    })
  }

  protected mapDeploymentsResponse({ data }: AxiosResponse<IDeploymentResponse[]>): Deployment[] {
    return data.map(this.mapDeployments)
  }

  protected mapDeploymentResponse({ data }: AxiosResponse<IDeploymentResponse>): Deployment {
    return this.mapDeployments(data)
  }

}

export const deploymentsApi = new DeploymentsApi()