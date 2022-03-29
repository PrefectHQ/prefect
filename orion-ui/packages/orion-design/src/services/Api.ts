// disabling because axios uses any in its method declarations
/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ApiRouteParams } from '@/models/ApiRouteParams'
import { Settings } from '@/services/Settings'
import { Require } from '@/types/utilities'

export type Route = string | ((params?: ApiRouteParams) => string)

export abstract class Api {
  // todo: can this will need to be defined by the server itself
  // https://github.com/PrefectHQ/orion/issues/667
  protected server: string = 'http://127.0.0.1:4200/api'

  private readonly _config: AxiosRequestConfig | null = null
  private _instance: AxiosInstance | null = null
  private _params: ApiRouteParams | undefined = undefined

  protected abstract route: Route

  public constructor(config?: AxiosRequestConfig) {
    if (config) {
      this._config = config
    }
  }

  protected instance(): AxiosInstance {
    if (this._instance) {
      return this._instance
    }

    return this._instance = axios.create(this.config())
  }

  protected config(): AxiosRequestConfig {
    if (this._config) {
      return this._config
    }

    return {
      baseURL: this.defaultApiUrl(),
    }
  }

  protected request<T = any, R = AxiosResponse<T>>(config: Require<AxiosRequestConfig, 'url' | 'method'>): Promise<R> {
    const urlWithRoute = this.withRoute(config.url, this._params)
    const configWithRoute = { ...config, url: urlWithRoute }
    const response: Promise<R> = this.instance().request(configWithRoute)

    this._params = undefined

    return response
  }

  protected get<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'GET', url })
  }

  protected delete<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'DELETE', url })
  }

  protected head<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'HEAD', url })
  }

  protected options<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'OPTIONS', url })
  }

  protected post<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'POST', url, data })
  }

  protected put<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'PUT', url, data })
  }

  protected patch<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.request({ ...config, method: 'PATCH', url, data })
  }

  protected withParams(params?: ApiRouteParams): this {
    if (params) {
      this._params = params
    }

    return this
  }

  protected getRoute(params?: ApiRouteParams): string {
    return typeof this.route === 'function' ? this.route(params) : this.route
  }

  private withRoute(url: string, params?: ApiRouteParams): string {
    const route = this.getRoute(params)

    return `${route}${url}`
  }

  private defaultApiUrl(): string {
    return Settings.apiUrl
  }

}
