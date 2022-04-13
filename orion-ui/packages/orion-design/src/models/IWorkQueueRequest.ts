import { IWorkQueueFilterResponse } from '@/models/IWorkQueueFilterResponse'

export type IWorkQueueRequest = Partial<{
  name: string | null,
  filter: IWorkQueueFilterResponse | null,
  description: string | null,
  is_paused: boolean | null,
  concurrency_limit: number | null,
}>