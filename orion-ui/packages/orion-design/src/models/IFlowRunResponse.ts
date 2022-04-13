import { IFlowRunnerResponse } from '@/models/IFlowRunnerResponse'
import { IStateResponse } from '@/models/IStateResponse'
import { StateType } from '@/models/StateType'
import { DateString } from '@/types/dates'

export type IFlowRunResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string | null,
  flow_id: string,
  state_id: string | null,
  deployment_id: string | null,
  flow_version: string | null,
  parameters: unknown,
  idempotency_key: string | null,
  context: unknown,
  empirical_policy: unknown,
  empirical_config: unknown,
  tags: string[] | null,
  parent_task_run_id: string | null,
  state_type: StateType | null,
  run_count: number | null,
  expected_start_time: DateString | null,
  next_scheduled_start_time: DateString | null,
  start_time: DateString | null,
  end_time: DateString | null,
  total_run_time: number | null,
  estimated_run_time: number | null,
  estimated_start_time_delta: number | null,
  auto_scheduled: boolean | null,
  flow_runner: IFlowRunnerResponse | null,
  state: IStateResponse | null,
}