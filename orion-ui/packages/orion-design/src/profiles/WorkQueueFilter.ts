import { IWorkQueueFilterResponse } from '@/models/IWorkQueueFilterResponse'
import { WorkQueueFilter } from '@/models/WorkQueueFilter'
import { Profile } from '@/services/Translate'

export const workQueueFilterProfile: Profile<IWorkQueueFilterResponse, WorkQueueFilter> = {
  toDestination(source) {
    return new WorkQueueFilter({
      tags: source.tags ?? [],
      deploymentIds: source.deployment_ids ?? [],
      flowRunnerTypes: source.flow_runner_types ?? [],
    })
  },
  toSource(destination) {
    return {
      'tags': destination.tags,
      'deployment_ids': destination.deploymentIds,
      'flow_runner_types': destination.flowRunnerTypes,
    }
  },
}