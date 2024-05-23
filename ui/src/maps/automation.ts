import { MapFunction } from '@/services/mapper'
import { Automation } from '@/types/automation'
import { AutomationCreate } from '@/types/automationCreate'
import { AutomationCreateRequest } from '@/types/automationCreateRequest'
import { AutomationResponse } from '@/types/automationResponse'

export const mapAutomationResponseToAutomation: MapFunction<AutomationResponse, Automation> = function(source) {
  return new Automation({
    id: source.id,
    name: source.name,
    description: source.description,
    enabled: source.enabled,
    trigger: this.map('AutomationTriggerResponse', source.trigger, 'AutomationTrigger'),
    actions: this.map('AutomationActionResponse', source.actions, 'AutomationAction'),
  })
}

export const mapAutomationCreateToAutomationCreateRequest: MapFunction<AutomationCreate, AutomationCreateRequest> = function(source) {
  return {
    name: source.name,
    description: source.description,
    enabled: source.enabled,
    trigger: this.map('AutomationTrigger', source.trigger, 'AutomationTriggerRequest'),
    actions: this.map('AutomationAction', source.actions, 'AutomationActionRequest'),
  }
}