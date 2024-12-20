import { Api } from '@prefecthq/prefect-ui-library'
import { ServerSettings } from '@/models/ServerSettings'
import { UiSettings } from './uiSettings'

export class AdminApi extends Api {
  protected override routePrefix = '/admin'

  public getSettings(): Promise<ServerSettings> {
    return this.get<ServerSettings>('/settings').then(({ data }) => data)
  }

  public async getVersion(): Promise<string> {
    return await this.get<string>('/version').then(({ data }) => data)
  }
  public async authCheck(): Promise<number> {
    const auth = await UiSettings.get('auth')
    if (!auth) {
      return 200
    }
    try {
      const res = await this.get('/version')
      return res.status
    } catch (error: any) {
      if (error.response) {
        return error.response.status
      }
      return 500
    }
  }
}
