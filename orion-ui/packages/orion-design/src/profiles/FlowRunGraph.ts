import { FlowRunGraph } from '@/models/FlowRunGraph'
import { IFlowRunGraphResponse } from '@/models/IFlowRunGraphResponse'
import { Profile, translate } from '@/services/Translate'

export const flowRunGraphProfile: Profile<IFlowRunGraphResponse, FlowRunGraph> = {
  toDestination(source) {
    return new FlowRunGraph({
      id: source.id,
      expectedStartTime: source.expected_start_time ? new Date(source.expected_start_time) : null,
      startTime: source.start_time ? new Date(source.start_time) : null,
      endTime: source.end_time ? new Date(source.end_time) : null,
      totalRunTime: source.total_run_time,
      estimatedRunTime: source.estimated_run_time,
      upstreamDependencies: source.upstream_dependencies.map(x => {
        return {
          id: x.id,
          inputType: x.input_type,
        }
      }),
      state: (this as typeof translate).toDestination('IStateResponse:IState', source.state),
    })
  },
  toSource(destination) {
    return {
      'id': destination.id,
      'expected_start_time': destination.expectedStartTime?.toISOString() ?? null,
      'start_time': destination.startTime?.toISOString() ?? null,
      'end_time': destination.endTime?.toISOString() ?? null,
      'total_run_time': destination.totalRunTime,
      'estimated_run_time': destination.estimatedRunTime,
      'upstream_dependencies': destination.upstreamDependencies.map(x => {
        return {
          'id': x.id,
          'input_type': x.inputType,
        }
      }),
      'state': (this as typeof translate).toSource('IStateResponse:IState', destination.state!),
    }
  },
}