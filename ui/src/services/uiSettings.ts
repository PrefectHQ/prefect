import axios from 'axios'
import { mapper } from '@/services/mapper'
import { SettingsResponse } from '@/types/settingsResponse'
import { MODE, BASE_URL } from '@/utilities/meta'
import { FeatureFlag } from '@/utilities/permissions'

export type Settings = {
  apiUrl: string,
  csrfEnabled: boolean,
  auth: string | null,
  flags: FeatureFlag[],
  defaultUi: 'v1' | 'v2',
  availableUis: Array<'v1' | 'v2'>,
  v1BaseUrl: string | null,
  v2BaseUrl: string | null,
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeBaseUrl(baseUrl?: string): string {
  if (!baseUrl || baseUrl === '/') {
    return '/'
  }

  const normalizedBaseUrl = baseUrl.startsWith('/') ? baseUrl : `/${baseUrl}`
  return normalizedBaseUrl.replace(/\/+$/, '') || '/'
}

function normalizePathname(pathname: string): string {
  if (!pathname || pathname === '/') {
    return '/'
  }

  return pathname.startsWith('/') ? pathname : `/${pathname}`
}

function getVisibleBasePrefix(
  pathname: string,
  currentBaseUrl: string,
  currentRelativePathname?: string,
): string {
  const normalizedPathname = normalizePathname(pathname)
  const normalizedCurrentBaseUrl = normalizeBaseUrl(currentBaseUrl)
  const normalizedRelativePathname = currentRelativePathname
    ? normalizePathname(currentRelativePathname)
    : undefined

  if (normalizedRelativePathname) {
    if (normalizedRelativePathname === '/' && normalizedCurrentBaseUrl === '/') {
      return normalizedPathname === '/' ? '' : normalizedPathname
    }

    const visibleCurrentPath = normalizedRelativePathname === '/'
      ? normalizedCurrentBaseUrl
      : normalizedCurrentBaseUrl === '/'
        ? normalizedRelativePathname
        : `${normalizedCurrentBaseUrl}${normalizedRelativePathname}`

    if (normalizedPathname === visibleCurrentPath) {
      return ''
    }

    if (normalizedPathname.endsWith(visibleCurrentPath)) {
      return normalizedPathname.slice(0, -visibleCurrentPath.length)
    }
  }

  if (normalizedCurrentBaseUrl === '/') {
    return ''
  }

  const match = normalizedPathname.match(
    new RegExp(`^(.*?)${escapeRegExp(normalizedCurrentBaseUrl)}(?:/|$)`),
  )

  return match?.[1] ?? ''
}

export function resolveUiSettingsBaseUrl(
  baseUrl: string | undefined,
  pathname: string,
  currentRelativePathname?: string,
): string {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
  const prefix = getVisibleBasePrefix(
    pathname,
    normalizedBaseUrl,
    currentRelativePathname,
  )

  if (!prefix) {
    return normalizedBaseUrl
  }

  if (normalizedBaseUrl === '/') {
    return prefix
  }

  return `${prefix}${normalizedBaseUrl}`
}

export class UiSettings {
  public static settings: Settings | null = null

  private static promise: Promise<Settings> | null = null
  private static readonly baseUrl = MODE() === 'development' ? 'http://127.0.0.1:4200' : BASE_URL()

  private static getBaseUrl(currentRelativePathname?: string): string | undefined {
    if (MODE() === 'development') {
      return this.baseUrl
    }

    const visibleBaseUrl = resolveUiSettingsBaseUrl(
      this.baseUrl,
      window.location.pathname,
      currentRelativePathname,
    )

    return visibleBaseUrl === '/' ? undefined : visibleBaseUrl
  }

  public static async load(currentRelativePathname?: string): Promise<Settings> {
    if (this.settings !== null) {
      return this.settings
    }

    if (this.promise !== null) {
      return this.promise
    }

    this.promise = axios.get<SettingsResponse>('/ui-settings', {
      baseURL: this.getBaseUrl(currentRelativePathname),
    })
      .then(({ data }) => mapper.map('SettingsResponse', data, 'Settings'))

    try {
      const settings = await this.promise
      this.settings = settings
      return settings
    } catch (error) {
      this.promise = null
      throw error
    }
  }

  public static async loadOptional(currentRelativePathname?: string): Promise<Settings | null> {
    try {
      return await this.load(currentRelativePathname)
    } catch {
      return null
    }
  }

  public static async get<T extends keyof Settings>(
    setting: T,
    defaultValue?: Settings[T],
    currentRelativePathname?: string,
  ): Promise<Settings[T]> {
    await this.load(currentRelativePathname)

    const value = this.settings?.[setting]

    if (value === undefined) {
      if (defaultValue !== undefined) {
        return defaultValue
      }

      throw `UI setting "${setting}" does not exist and no default was provided.`
    }

    return value
  }
}

export const uiSettings: {
  getApiUrl: () => Promise<string>,
  getFeatureFlags: (currentRelativePathname?: string) => Promise<FeatureFlag[]>,
} = {
  getApiUrl: () => {
    return UiSettings.get('apiUrl')
  },
  getFeatureFlags: (currentRelativePathname?: string) => {
    return UiSettings.get('flags', undefined, currentRelativePathname)
  },
}
