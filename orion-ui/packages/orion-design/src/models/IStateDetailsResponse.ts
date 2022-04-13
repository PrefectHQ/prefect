import { DateString } from '@/types/dates'

export type IStateDetailsResponse = {
  flow_run_id: string | null,
  task_run_id: string | null,
  child_flow_run_id: string | null,
  scheduled_time: DateString | null,
  cache_key: string | null,
  cache_expiration: string | null,
}