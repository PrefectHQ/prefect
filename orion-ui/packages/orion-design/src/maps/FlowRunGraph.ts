import { FlowRunGraph } from '@/models/FlowRunGraph'
import { IFlowRunGraphResponse } from '@/models/IFlowRunGraphResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowRunGraphResponseToFlowRunGraph: MapFunction<IFlowRunGraphResponse, FlowRunGraph> = function(source: IFlowRunGraphResponse): FlowRunGraph {
  return new FlowRunGraph({
    id: source.id,
    expectedStartTime: source.expected_start_time ? this.map('string', source.expected_start_time, 'Date') : null,
    startTime: source.start_time ? this.map('string', source.start_time, 'Date') : null,
    endTime: source.end_time ? this.map('string', source.end_time, 'Date') : null,
    totalRunTime: source.total_run_time,
    estimatedRunTime: source.estimated_run_time,
    upstreamDependencies: source.upstream_dependencies.map(x => {
      return {
        id: x.id,
        inputType: x.input_type,
      }
    }),
    state: this.map('IStateResponse', source.state, 'IState'),
  })
}

export const mapFlowRunGraphToIFlowRunGraphResponse: MapFunction<FlowRunGraph, IFlowRunGraphResponse> = function(source: FlowRunGraph): IFlowRunGraphResponse {
  return {
    'id': source.id,
    'expected_start_time': source.expectedStartTime ? this.map('Date', source.expectedStartTime, 'string') : null,
    'start_time': source.startTime ? this.map('Date', source.startTime, 'string') : null,
    'end_time': source.endTime ? this.map('Date', source.endTime, 'string') : null,
    'total_run_time': source.totalRunTime,
    'estimated_run_time': source.estimatedRunTime,
    'upstream_dependencies': source.upstreamDependencies.map(x => {
      return {
        'id': x.id,
        'input_type': x.inputType,
      }
    }),
    'state': this.map('IState', source.state!, 'IStateResponse'),
  }
}