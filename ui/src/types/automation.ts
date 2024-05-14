import { AutomationAction, AutomationTrigger, Automation as BaseAutomation, IAutomation as BaseIAutomation } from '@prefecthq/prefect-ui-library'

export interface IAutomation extends BaseIAutomation {
  trigger: AutomationTrigger,
  actions: AutomationAction[],
}

export class Automation extends BaseAutomation {
  public trigger: AutomationTrigger
  public actions: AutomationAction[]

  public constructor(automation: IAutomation) {
    super(automation)
    this.trigger = automation.trigger
    this.actions = automation.actions
  }
}

export type AutomationFormValues = {
  id?: string,
  name?: string,
  description?: string,
  trigger?: AutomationTrigger,
  actions?: AutomationAction[],
  enabled?: boolean,
}

export type AutomationActionFormValues = AutomationFormValues & {
  trigger: AutomationTrigger,
}

export function isAutomationActionFormValues(value: AutomationFormValues): value is AutomationActionFormValues {
  return Boolean(value.trigger)
}