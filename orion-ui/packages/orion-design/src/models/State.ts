import { IFlowData } from '@/models/FlowData'
import { IStateDetails } from '@/models/StateDetails'

export interface IState {
  id: string,
  type: string,
  message: string,
  stateDetails: IStateDetails | null,
  data: IFlowData | null,
  timestamp: string,
  name: string,
}