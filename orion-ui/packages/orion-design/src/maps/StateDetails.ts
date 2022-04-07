import { IStateDetailsResponse } from '@/models/IStateDetailsResponse'
import { IStateDetails } from '@/models/StateDetails'
import { MapFunction } from '@/services/Mapper'

export const mapIStateDetailsResponseToIStateDetails: MapFunction<IStateDetailsResponse, IStateDetails> = function(source: IStateDetailsResponse): IStateDetails {
  return {
    flowRunId: source.flow_run_id,
    taskRunId: source.task_run_id,
    childFlowRunId: source.child_flow_run_id,
    cacheKey: source.cache_key,
    scheduledTime: this.map('string', source.scheduled_time, 'Date'),
    cacheExpiration: this.map('string', source.cache_expiration, 'Date'),
  }
}

export const mapIStateDetailsToIStateDetailsResponse: MapFunction<IStateDetails, IStateDetailsResponse> = function(source: IStateDetails): IStateDetailsResponse {
  return {
    'flow_run_id': source.flowRunId,
    'task_run_id': source.taskRunId,
    'child_flow_run_id': source.childFlowRunId,
    'cache_key': source.cacheKey,
    'scheduled_time': this.map('Date', source.scheduledTime, 'string'),
    'cache_expiration': this.map('Date', source.cacheExpiration, 'string'),
  }
}