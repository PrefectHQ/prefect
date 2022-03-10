import { TaskRunInputType } from '@/models/FlowRunGraph'
import { IStateResponse } from '@/services/StatesApi'

export type IFlowRunGraphResponse = {
  id: string,
  upstream_dependencies: {
    id: string,
    input_type: TaskRunInputType,
  }[],
  state: IStateResponse,
}