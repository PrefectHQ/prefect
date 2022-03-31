import { AxiosResponse } from 'axios'
import { InjectionKey } from 'vue'
import { Deployment } from '@/models/Deployment'
import { Flow } from '@/models/Flow'
import { FlowData } from '@/models/FlowData'
import { FlowRunner } from '@/models/FlowRunner'
import { ICreateFlowRunRequest } from '@/models/ICreateFlowRunRequest'
import { IDeploymentResponse } from '@/models/IDeploymentResponse'
import { IFlowDataResponse } from '@/models/IFlowDataResponse'
import { IFlowResponse } from '@/models/IFlowResponse'
import { IFlowRunnerResponse } from '@/models/IFlowRunnerResponse'
import { IScheduleResponse, isCronScheduleResponse, isIntervalScheduleResponse, isRRuleScheduleResponse } from '@/models/IScheduleResponse'
import { CronSchedule, IntervalSchedule, RRuleSchedule, Schedule } from '@/models/Schedule'
import { Api, ApiRoute } from '@/services/Api'
import { UnionFilters } from '@/services/Filter'

export class DeploymentsApi extends Api {

  protected override route: ApiRoute = '/deployments'

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

  public deleteDeployment(deploymentId: string): Promise<void> {
    return this.delete(`/${deploymentId}`)
  }

  // this is public temporarily to be used in ListItemDeployment in orion-ui which is still using the old models
  public mapDeployment(data: IDeploymentResponse): Deployment {
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
    return data.map(x => this.mapDeployment(x))
  }

  protected mapDeploymentResponse({ data }: AxiosResponse<IDeploymentResponse>): Deployment {
    return this.mapDeployment(data)
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

export const deploymentsApiKey: InjectionKey<DeploymentsApi> = Symbol('deploymentsApiKey')
