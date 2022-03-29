
import axios, { AxiosResponse } from 'axios'
import { MODE } from '@/utilities/meta'

type SettingsResponse = {
  api_url: string,
}

type Settings = {
  apiUrl: string,
}

export class SettingsApi {
  public get(): Promise<Settings> {
    return axios.get<SettingsResponse>('/api_settings', {
      baseURL: MODE() === 'development' ? 'http://127.0.0.1:4200' : window.location.origin,
    }).then(response => mapSettingsResponse(response))
  }
}

function mapSettingsResponse(response: AxiosResponse<SettingsResponse>): Settings {
  const settings = response.data

  return {
    apiUrl: settings.api_url,
  }
}

export const settingsApi = new SettingsApi()