import { IWorkQueueFilterResponse } from '@/models/IWorkQueueFilterResponse'
import { DateString } from '@/types/dates'

export type IWorkQueueResponse = {
  id: string,
  created: DateString,
  updated: DateString,
  name: string,
  filter: IWorkQueueFilterResponse,
  description: string | null,
  is_paused: boolean | null,
  concurrency_limit: number | null,
}