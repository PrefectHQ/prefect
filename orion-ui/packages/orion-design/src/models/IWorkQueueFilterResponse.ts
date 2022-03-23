import { FlowRunnerType } from '@/types/FlowRunnerType'

export type IWorkQueueFilterResponse = {
  tags: string[] | null,
  deployment_ids: string[] | null,
  flow_runner_types: FlowRunnerType[] | null,
}