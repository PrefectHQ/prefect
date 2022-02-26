import { IStateResponse } from '@/services/StatesApi'
import { TaskRunInputType } from '@/models'

export type IFlowRunGraphResponse = {
  id: string,
  upstream_dependencies: {
    id: string,
    input_type: TaskRunInputType,
  }[],
  state: IStateResponse,
}