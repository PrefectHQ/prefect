
import { StateType } from '@/models/StateType'

export type UiFlowRunHistory = {
  id: string,
  stateType: StateType,
  duration: number,
  lateness: number,
  timestamp: Date,
}