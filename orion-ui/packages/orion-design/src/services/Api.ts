// disabling because axios uses any in its method declarations
/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

export class Api {
  // todo: can this will need to be defined by the server itself
  // https://github.com/PrefectHQ/orion/issues/667
  protected server: string = 'http://localhost:4200'
  protected instance: AxiosInstance

  public constructor(routeOrConfig: string | AxiosRequestConfig) {
    let config: AxiosRequestConfig

    if (typeof routeOrConfig === 'string') {
      const route = routeOrConfig
      config = {
        baseURL: `http://localhost:4200${route}`,
      }
    } else {
      config = routeOrConfig
    }

    this.instance = axios.create(config)
  }

  protected request<T = any, R = AxiosResponse<T>>(config: AxiosRequestConfig): Promise<R> {
    return this.instance.request(config)
  }

  protected get<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.get(url, config)
  }

  protected delete<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.delete(url, config)
  }

  protected head<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.head(url, config)
  }

  protected options<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.options(url, config)
  }

  protected post<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    console.log('here', this.instance.post)
    return this.instance.post(url, data, config)
  }

  protected put<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.put(url, data, config)
  }

  protected patch<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.patch(url, data, config)
  }
}
