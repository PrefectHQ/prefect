import { FlowData } from '@/models/FlowData'
import { IFlowDataResponse } from '@/models/IFlowDataResponse'
import { Profile } from '@/services/Translate'

export const flowDataProfile: Profile<IFlowDataResponse, FlowData> = {
  toDestination(source) {
    return new FlowData({
      encoding: source.encoding,
      blob: source.blob,
    })
  },
  toSource(destination) {
    return {
      encoding: destination.encoding,
      blob: destination.blob,
    }
  },
}