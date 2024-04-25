import { randomId } from '@prefecthq/prefect-design'
import { Api, AxiosInstanceSetupHook, PrefectConfig, isApiErrorResponse } from '@prefecthq/prefect-ui-library'
import { CreateActions } from '@prefecthq/vue-compositions'
import { AxiosError, AxiosInstance, InternalAxiosRequestConfig, isAxiosError } from 'axios'
import { CsrfToken } from '@/models/CsrfToken'
import { mapper } from '@/services/mapper'
import { CsrfTokenResponse } from '@/types/csrfTokenResponse'

const MAX_RETRIES: number = 1

export class CsrfTokenApi extends Api {
  public csrfToken?: CsrfToken
  public clientId: string = randomId()
  public csrfSupportEnabled = true
  private refreshTimeout: ReturnType<typeof setTimeout> | null = null
  private ongoingRefresh: Promise<void> | null = null

  public constructor(apiConfig: PrefectConfig, instanceSetupHook: AxiosInstanceSetupHook | null = null) {
    super(apiConfig, instanceSetupHook)
    this.startBackgroundTokenRefresh()
  }

  public async addCsrfHeaders(config: InternalAxiosRequestConfig): Promise<void> {
    if (this.csrfSupportEnabled) {
      const csrfToken = await this.getCsrfToken()
      config.headers['Prefect-Csrf-Token'] = csrfToken.token
      config.headers['Prefect-Csrf-Client'] = this.clientId
      config.headers['Prefect-Csrf-Retry-Count'] = config.headers['Prefect-Csrf-Retry-Count'] ?? '0'
    }
  }

  private async getCsrfToken(): Promise<CsrfToken> {
    if (this.shouldRefreshToken()) {
      await this.refreshCsrfToken()
    }

    if (!this.csrfToken) {
      throw new Error('CSRF token not available')
    }

    return this.csrfToken
  }

  private refreshCsrfToken(force: boolean = false): Promise<void> {
    if (!force && !this.shouldRefreshToken()) {
      return this.ongoingRefresh ?? Promise.resolve()
    }

    if (this.ongoingRefresh) {
      return this.ongoingRefresh
    }

    const refresh = async (): Promise<void> => {
      try {
        const response = await this.get<CsrfTokenResponse>(`/csrf-token?client=${this.clientId}`)
        this.csrfToken = mapper.map('CsrfTokenResponse', response.data, 'CsrfToken')
        this.ongoingRefresh = null
      } catch (error) {
        this.ongoingRefresh = null

        if (this.isUnconfiguredServer(error)) {
          this.disableCsrfSupport()
        } else {
          console.error('Failed to refresh CSRF token:', error)
          throw new Error('Failed to refresh CSRF token')
        }
      }
    }

    this.ongoingRefresh = refresh()
    return this.ongoingRefresh
  }

  private shouldRefreshToken(): boolean {
    if (!this.csrfSupportEnabled) {
      return false
    }

    if (!this.csrfToken) {
      return true
    }

    return new Date() > this.csrfToken.expiration
  }

  private isUnconfiguredServer(error: unknown): boolean {
    if (!isApiErrorResponse(error)) {
      return false
    }

    return error.response.status === 422 && error.response.data.detail.includes('CSRF protection is disabled')
  }

  public isInvalidCsrfToken(error: AxiosError): boolean {
    if (!isApiErrorResponse(error)) {
      return false
    }

    return error.response.status === 403 && error.response.data.detail.includes('Invalid CSRF token')
  }

  private disableCsrfSupport(): void {
    this.csrfSupportEnabled = false
  }

  private startBackgroundTokenRefresh(): void {
    const calculateTimeoutDuration = (): number => {
      if (this.csrfToken) {
        const now = new Date()
        const expiration = new Date(this.csrfToken.expiration)
        const issuedAt = this.csrfToken.issued
        const lifetime = expiration.getTime() - issuedAt.getTime()
        const refreshThreshold = issuedAt.getTime() + lifetime * 0.75
        const durationUntilRefresh = refreshThreshold - now.getTime()

        return durationUntilRefresh
      }

      // If we don't have token data cause an immediate refresh
      return 0
    }

    const refreshTask = async (): Promise<void> => {
      if (this.csrfSupportEnabled) {
        await this.refreshCsrfToken(true)
        this.refreshTimeout = setTimeout(refreshTask, calculateTimeoutDuration())
      }
    }

    this.refreshTimeout = setTimeout(refreshTask, calculateTimeoutDuration())
  }
}

export function setupCsrfInterceptor(csrfTokenApi: CreateActions<CsrfTokenApi>, axiosInstance: AxiosInstance): void {
  axiosInstance.interceptors.request.use(async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
    const method = config.method?.toLowerCase()

    if (method && ['post', 'patch', 'put', 'delete'].includes(method)) {
      await csrfTokenApi.addCsrfHeaders(config)
    }

    return config
  })

  axiosInstance.interceptors.response.use(undefined, async (error: AxiosError) => {
    if (isAxiosError(error) && csrfTokenApi.isInvalidCsrfToken(error)) {
      const { config } = error

      if (config?.headers['Prefect-Csrf-Retry-Count']) {
        const retryCount = parseInt(config.headers['Prefect-Csrf-Retry-Count'], 10)
        if (retryCount < MAX_RETRIES) {
          await csrfTokenApi.addCsrfHeaders(config)
          config.headers['Prefect-Csrf-Retry-Count'] = (retryCount + 1).toString()
          return axiosInstance(config)
        }
      }
    }

    return Promise.reject(error)
  })
}
