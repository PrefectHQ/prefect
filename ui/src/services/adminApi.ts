import { Api } from '@prefecthq/prefect-ui-library'
import { ServerSettings } from '@/models/ServerSettings'

export class AdminApi extends Api {
  protected override routePrefix = '/admin'

  public getSettings(): Promise<ServerSettings> {
    return this.get<ServerSettings>('/settings').then(({ data }) => data)
  }

  public async getVersion(): Promise<string> {
    return await this.get<string>('/version').then(({ data }) => data)
  }
}