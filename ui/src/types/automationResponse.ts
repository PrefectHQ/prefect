import { AutomationActionResponse, AutomationResponse as BaseAutomationResponse, AutomationTriggerResponse } from '@prefecthq/prefect-ui-library'

export type AutomationResponse = BaseAutomationResponse & {
  created: string,
  updated: string,
  trigger: AutomationTriggerResponse,
  actions: AutomationActionResponse[],
}