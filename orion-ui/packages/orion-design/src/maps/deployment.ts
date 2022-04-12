import { Deployment } from '@/models/Deployment'
import { IDeploymentResponse } from '@/models/IDeploymentResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIDeploymentResponseToDeployment: MapFunction<IDeploymentResponse, Deployment> = function(source: IDeploymentResponse): Deployment {
  return new Deployment({
    id: source.id,
    created: this.map('string', source.created, 'Date'),
    updated: this.map('string', source.updated, 'Date'),
    name: source.name,
    flowId: source.flow_id,
    flowData: this.map('IFlowDataResponse', source.flow_data, 'FlowData'),
    schedule: this.map('IScheduleResponse', source.schedule, 'Schedule'),
    isScheduleActive: source.is_schedule_active,
    parameters: source.parameters,
    tags: source.tags,
    flowRunner: this.map('IFlowRunnerResponse', source.flow_runner, 'FlowRunner'),
  })
}

export const mapDeploymentToIDeploymentResponse: MapFunction<Deployment, IDeploymentResponse> = function(source: Deployment): IDeploymentResponse {
  return {
    'id': source.id,
    'created': this.map('Date', source.created, 'string'),
    'updated': this.map('Date', source.updated, 'string'),
    'name': source.name,
    'flow_id': source.flowId,
    'flow_data': this.map('FlowData', source.flowData, 'IFlowDataResponse'),
    'schedule': this.map('Schedule', source.schedule, 'IScheduleResponse'),
    'is_schedule_active': source.isScheduleActive,
    'parameters': source.parameters,
    'tags': source.tags,
    'flow_runner': this.map('FlowRunner', source.flowRunner, 'IFlowRunnerResponse'),
  }
}