import { AutomationsFilter, WorkspaceAutomationsApi } from '@prefecthq/prefect-ui-library'
import { mapper } from '@/services/mapper'
import { Automation } from '@/types/automation'
import { AutomationCreate } from '@/types/automationCreate'
import { AutomationResponse } from '@/types/automationResponse'

export class AutomationsApi extends WorkspaceAutomationsApi {

  public override async getAutomation(automationId: string): Promise<Automation> {
    const { data } = await this.get<AutomationResponse>(`/${automationId}`)

    return mapper.map('AutomationResponse', data, 'Automation')
  }

  public override async getAutomations(filter: AutomationsFilter = {}): Promise<Automation[]> {
    const { data } = await this.post<AutomationResponse[]>('/filter', filter)

    return mapper.map('AutomationResponse', data, 'Automation')
  }

  public async createAutomation(automation: AutomationCreate): Promise<Automation> {
    const request = mapper.map('AutomationCreate', automation, 'AutomationCreateRequest')
    const { data } = await this.post<AutomationResponse>('/', request)

    return mapper.map('AutomationResponse', data, 'Automation')
  }

  public updateAutomation(automationId: string, automation: AutomationCreate): Promise<void> {
    const request = mapper.map('AutomationCreate', automation, 'AutomationCreateRequest')

    return this.put(`/${automationId}`, request)
  }

  public async getResourceAutomations(resourceId: string): Promise<Automation[]> {
    const { data } = await this.get<AutomationResponse[]>(`related-to/${resourceId}`)

    return mapper.map('AutomationResponse', data, 'Automation')
  }
}