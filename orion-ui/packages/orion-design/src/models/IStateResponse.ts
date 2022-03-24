import { IFlowData } from '@/models/FlowData'
import { IStateDetails } from '@/models/StateDetails'

export type IStateResponse = {
  id: string,
  type: string,
  message: string,
  state_details: IStateDetails | null,
  data: IFlowData | null,
  timestamp: string,
  name: string,
}