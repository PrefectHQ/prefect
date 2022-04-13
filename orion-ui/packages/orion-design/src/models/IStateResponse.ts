import { IFlowData } from '@/models/FlowData'
import { IStateDetailsResponse } from '@/models/IStateDetailsResponse'

export type IStateResponse = {
  id: string,
  type: string,
  message: string,
  state_details: IStateDetailsResponse | null,
  data: IFlowData | null,
  timestamp: string,
  name: string,
}