import { Flow } from '@/models/Flow'
import { IFlowResponse } from '@/models/IFlowResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowResponseToFlow: MapFunction<IFlowResponse, Flow> = function(source: IFlowResponse): Flow {
  return new Flow({
    id: source.id,
    name: source.name,
    tags: source.tags,
    created: this.map('string', source.created, 'Date'),
    updated: this.map('string', source.updated, 'Date'),
  })
}

export const mapFlowToIFlowResponse: MapFunction<Flow, IFlowResponse> = function(source: Flow): IFlowResponse {
  return {
    id: source.id,
    name: source.name,
    tags: source.tags,
    created: this.map('Date', source.created, 'string'),
    updated: this.map('Date', source.updated, 'string'),
  }
}