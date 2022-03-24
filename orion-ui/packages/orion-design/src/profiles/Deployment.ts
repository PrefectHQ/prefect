import { Deployment } from '@/models/Deployment'
import { IDeploymentResponse } from '@/models/IDeploymentResponse'
import { Profile, translate } from '@/services/Translate'

export const deploymentProfile: Profile<IDeploymentResponse, Deployment> = {
  toDestination(source) {
    return new Deployment({
      id: source.id,
      created: new Date(source.created),
      updated: new Date(source.updated),
      name: source.name,
      flowId: source.flow_id,
      flowData: (this as typeof translate).toDestination('IFlowDataResponse:FlowData', source.flow_data),
      schedule: source.schedule ? (this as typeof translate).toDestination('IScheduleResponse:Schedule', source.schedule) : null,
      isScheduleActive: source.is_schedule_active,
      parameters: source.parameters,
      tags: source.tags,
      flowRunner: (this as typeof translate).toDestination('IFlowRunnerResponse:FlowRunner', source.flow_runner),
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'created': destination.created.toISOString(),
      'updated': destination.updated.toISOString(),
      'name': destination.name,
      'flow_id': destination.flowId,
      'flow_data': (this as typeof translate).toSource('IFlowDataResponse:FlowData', destination.flowData),
      'schedule': destination.schedule ? (this as typeof translate).toSource('IScheduleResponse:Schedule', destination.schedule) : null,
      'is_schedule_active': destination.isScheduleActive,
      'parameters': destination.parameters,
      'tags': destination.tags,
      'flow_runner': (this as typeof translate).toSource('IFlowRunnerResponse:FlowRunner', destination.flowRunner!),
    }
  },
}