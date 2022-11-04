
import axios, { AxiosResponse } from 'axios'
import { MODE, BASE_URL } from '@/utilities/meta'

type SettingsResponse = {
  api_url: string,
}

type Settings = {
  apiUrl: string,
}

export class UiSettings {
  public static settings: Settings | null = null

  private static promise: Promise<Settings> | null = null
  private static readonly baseUrl = MODE() === 'development' ? 'http://127.0.0.1:4200' : BASE_URL() ?? window.location.origin
  public static async load(): Promise<Settings> {
    if (this.settings !== null) {
      return this.settings
    }

    if (this.promise !== null) {
      return this.promise
    }

    this.promise = new Promise(resolve => {
      return axios.get<SettingsResponse>('/ui-settings', {
        baseURL: this.baseUrl,
      }).then(mapSettingsResponse).then(resolve)
    })

    const settings = await this.promise

    return this.settings = settings
  }

  public static async get<T extends keyof Settings>(setting: T, defaultValue?: Settings[T]): Promise<Settings[T]> {
    await this.load()

    const value = this.settings?.[setting]

    if (value === undefined) {
      if (defaultValue) {
        return defaultValue
      }

      throw `UI setting "${setting}" does not exist and no default was provided.`
    }

    return value
  }
}

function mapSettingsResponse(response: AxiosResponse<SettingsResponse>): Settings {
  const settings = response.data

  return {
    apiUrl: settings.api_url,
  }
}