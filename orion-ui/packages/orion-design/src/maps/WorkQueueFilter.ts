import { IWorkQueueFilterResponse } from '@/models/IWorkQueueFilterResponse'
import { WorkQueueFilter } from '@/models/WorkQueueFilter'
import { MapFunction } from '@/services/Mapper'

export const mapIWorkQueueFilterResponseToWorkQueueFilter: MapFunction<IWorkQueueFilterResponse, WorkQueueFilter> = function(source: IWorkQueueFilterResponse): WorkQueueFilter {
  return new WorkQueueFilter({
    tags: source.tags ?? [],
    deploymentIds: source.deployment_ids ?? [],
    flowRunnerTypes: source.flow_runner_types ?? [],
  })
}

export const mapWorkQueueFilterToIWorkQueueFilterResponse: MapFunction<WorkQueueFilter, IWorkQueueFilterResponse> = function(source: WorkQueueFilter): IWorkQueueFilterResponse {
  return {
    'tags': source.tags,
    'deployment_ids': source.deploymentIds,
    'flow_runner_types': source.flowRunnerTypes,
  }
}