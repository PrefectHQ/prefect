import { TaskRunInputType } from '@/models/FlowRunGraph'
import { IStateResponse } from '@/models/IStateResponse'
import { DateString } from '@/types/dates'

export type IFlowRunGraphResponse = {
  id: string,
  upstream_dependencies: {
    id: string,
    input_type: TaskRunInputType,
  }[],
  state: IStateResponse,
  expected_start_time: DateString | null,
  start_time: DateString | null,
  end_time: DateString | null,
  total_run_time: number | null,
  estimated_run_time: number | null,
}