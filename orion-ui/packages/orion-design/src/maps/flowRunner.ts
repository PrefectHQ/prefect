import { FlowRunner } from '@/models/FlowRunner'
import { IFlowRunnerResponse } from '@/models/IFlowRunnerResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowRunnerResponseToFlowRunner: MapFunction<IFlowRunnerResponse, FlowRunner> = function(source: IFlowRunnerResponse): FlowRunner {
  return new FlowRunner({
    type: source.type,
    config: source.config,
  })
}

export const mapFlowRunnerToIFlowRunnerResponse: MapFunction<FlowRunner, IFlowRunnerResponse> = function(source: FlowRunner): IFlowRunnerResponse {
  return {
    type: source.type,
    config: source.config,
  }
}