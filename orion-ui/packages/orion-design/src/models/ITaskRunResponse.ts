import { IEmpiricalPolicyResponse } from '@/models/IEmpiricalPolicyResponse'
import { IStateResponse } from '@/models/IStateResponse'
import { ITaskInputResponse } from '@/models/ITaskInputResponse'
import { StateType } from '@/models/StateType'
import { DateString } from '@/types/dates'

export type ITaskRunResponse = {
  id: string,
  created: string,
  updated: string,
  name: string | null,
  flow_run_id: string,
  task_key: string,
  dynamic_key: string,
  cache_key: string | null,
  cache_expiration: DateString | null,
  task_version: string | null,
  empirical_policy: IEmpiricalPolicyResponse | null,
  tags: string[] | null,
  state_id: string | null,
  task_inputs: Record<string, ITaskInputResponse[]> | null,
  state_type: StateType | null,
  run_count: number | null,
  expected_start_time: DateString | null,
  next_scheduled_start_time: DateString | null,
  start_time: DateString | null,
  end_time: DateString | null,
  total_run_time: number | null,
  estimated_run_time: number | null,
  estimated_start_time_delta: number | null,
  state: IStateResponse | null,
}