import { IStateResponse } from '@/services/StatesApi'

export type IFlowRunGraphResponse = {
  id: string,
  upstream_dependencies: {
    id: string,
    input_type: 'constant' | 'parameter' | 'task_run',
  }[],
  state: IStateResponse,
}