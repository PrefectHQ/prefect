import { AutomationActionResponse, AutomationTriggerResponse } from '@prefecthq/prefect-ui-library'

export type AutomationCreateRequest = {
  name: string,
  description: string | null,
  enabled: boolean,
  trigger: AutomationTriggerResponse,
  actions: AutomationActionResponse[],
}