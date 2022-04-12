import { FlowData } from '@/models/FlowData'
import { IFlowDataResponse } from '@/models/IFlowDataResponse'
import { MapFunction } from '@/services/Mapper'

export const mapIFlowDataResponseToFlowData: MapFunction<IFlowDataResponse, FlowData> = function(source: IFlowDataResponse): FlowData {
  return new FlowData({
    encoding: source.encoding,
    blob: source.blob,
  })
}

export const mapFlowDataToIFlowDataResponse: MapFunction<FlowData, IFlowDataResponse> = function(source: FlowData): IFlowDataResponse {
  return {
    encoding: source.encoding,
    blob: source.blob,
  }
}