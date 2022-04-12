
import { StateType } from '@/models/StateType'

export type UiFlowRunHistoryResponse = {
  id: string,
  state_type: StateType,
  duration: number,
  lateness: number,
  timestamp: string,
}