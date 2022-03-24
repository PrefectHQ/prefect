import { IStateDetailsResponse } from '@/models/IStateDetailsResponse'
import { IStateDetails } from '@/models/StateDetails'
import { Profile } from '@/services/Translate'

export const stateDetailsProfile: Profile<IStateDetailsResponse, IStateDetails> = {
  toDestination(source) {
    return {
      flowRunId: source.flow_run_id,
      taskRunId: source.task_run_id,
      childFlowRunId: source.child_flow_run_id,
      cacheKey: source.cache_key,
      scheduledTime: source.scheduled_time ? new Date(source.scheduled_time) : null,
      cacheExpiration: source.cache_expiration ? new Date(source.cache_expiration) : null,
    }
  },
  toSource(destination: IStateDetails) {
    return {
      'flow_run_id': destination.flowRunId,
      'task_run_id': destination.taskRunId,
      'child_flow_run_id': destination.childFlowRunId,
      'cache_key': destination.cacheKey,
      'scheduled_time': destination.scheduledTime?.toISOString() ?? null,
      'cache_expiration': destination.cacheExpiration?.toISOString() ?? null,
    }
  },
}