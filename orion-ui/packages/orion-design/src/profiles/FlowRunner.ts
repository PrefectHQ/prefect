import { FlowRunner } from '@/models/FlowRunner'
import { IFlowRunnerResponse } from '@/models/IFlowRunnerResponse'
import { Profile } from '@/services/Translate'

export const flowRunnerProfile: Profile<IFlowRunnerResponse, FlowRunner> = {
  toDestination(source) {
    return new FlowRunner({
      type: source.type,
      config: source.config,
    })
  },
  toSource(destination) {
    return {
      type: destination.type,
      config: destination.config,
    }
  },
}