import { Settings } from '@/services/uiSettings'

export type UiVersion = 'v1' | 'v2'

export const UI_VERSION_COOKIE_NAME = 'prefect_ui_version'
export const V2_PROMO_DISMISSED_STORAGE_KEY = 'prefect-v2-promo-dismissed'

const ONE_YEAR_IN_SECONDS = 60 * 60 * 24 * 365
const V2_LANDING_PATH = '/dashboard'

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeBaseUrl(baseUrl: string | null): string {
  if (!baseUrl || baseUrl === '/') {
    return '/'
  }

  return baseUrl.replace(/\/+$/, '')
}

function normalizePathname(pathname: string): string {
  if (!pathname || pathname === '/') {
    return '/'
  }

  return pathname.startsWith('/') ? pathname : `/${pathname}`
}

function buildUiUrl(baseUrl: string | null, pathname: string, search: string, hash: string): string {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
  const normalizedPathname = pathname.startsWith('/') ? pathname : `/${pathname}`

  if (normalizedBaseUrl === '/') {
    return `${normalizedPathname}${search}${hash}`
  }

  if (normalizedPathname === '/') {
    return `${normalizedBaseUrl}${search}${hash}`
  }

  return `${normalizedBaseUrl}${normalizedPathname}${search}${hash}`
}

function getUiPathPrefix(pathname: string, currentBaseUrl: string | null): string {
  const normalizedCurrentBaseUrl = normalizeBaseUrl(currentBaseUrl)

  if (normalizedCurrentBaseUrl === '/') {
    return ''
  }

  const match = (pathname || '/').match(
    new RegExp(`^(.*?)${escapeRegExp(normalizedCurrentBaseUrl)}(?:/|$)`),
  )
  return match?.[1] ?? ''
}

function getVisibleBasePrefix(
  pathname: string,
  currentBaseUrl: string | null,
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

  return getUiPathPrefix(normalizedPathname, currentBaseUrl)
}

function resolveVisibleBaseUrl(
  baseUrl: string | null,
  pathname: string,
  currentBaseUrl: string | null = baseUrl,
  currentRelativePathname?: string,
): string {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl)
  const prefix = getVisibleBasePrefix(
    pathname,
    currentBaseUrl,
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

export function isUiAvailable(settings: Settings, version: UiVersion): boolean {
  return settings.availableUis.includes(version)
}

export function setPreferredUiVersion(
  settings: Settings,
  version: UiVersion,
  currentRelativePathname?: string,
): void {
  const cookiePath = resolveVisibleBaseUrl(
    settings.v1BaseUrl,
    window.location.pathname,
    settings.v1BaseUrl,
    currentRelativePathname,
  )
  document.cookie = `${UI_VERSION_COOKIE_NAME}=${version}; Path=${cookiePath}; Max-Age=${ONE_YEAR_IN_SECONDS}; SameSite=Lax`
}

export function buildSwitchToV2Url(
  settings: Settings,
  currentRelativePathname?: string,
): string {
  const v2BaseUrl = resolveVisibleBaseUrl(
    settings.v2BaseUrl,
    window.location.pathname,
    settings.v1BaseUrl,
    currentRelativePathname,
  )
  return buildUiUrl(
    v2BaseUrl,
    V2_LANDING_PATH,
    '',
    '',
  )
}

export function switchToV2Ui(
  settings: Settings,
  currentRelativePathname?: string,
): void {
  setPreferredUiVersion(settings, 'v2', currentRelativePathname)
  window.location.assign(buildSwitchToV2Url(settings, currentRelativePathname))
}
