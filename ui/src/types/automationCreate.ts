import { AutomationAction, AutomationTrigger } from '@prefecthq/prefect-ui-library'

export type AutomationCreate = {
  name: string,
  description: string | null,
  enabled: boolean,
  trigger: AutomationTrigger,
  actions: AutomationAction[],
}