import { IState } from '@/models/State'
import { MockFunction } from '@/services/Mocker'

export const randomState: MockFunction<IState> = function(state?: Partial<IState>) {
  return {
    id: state?.id ?? this.create('string'),
    type: state?.type ?? this.create('stateType'),
    message: state?.message ?? this.create('string'),
    stateDetails: state?.stateDetails ?? {
      flowRunId: this.create('string'),
      taskRunId: this.create('string'),
      childFlowRunId: this.create('string'),
      scheduledTime: this.create('date'),
      cacheKey: this.create('string'),
      cacheExpiration: this.create('date'),
    },
    data: state?.data ?? {
      encoding: this.create('string'),
      blob: this.create('string'),
    },
    timestamp: state?.timestamp ?? this.create('string'),
    name: state?.name ?? this.create('string'),
  }
}