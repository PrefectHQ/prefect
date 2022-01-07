// disabling because axios uses any in its method declarations
/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

export class Api {
  protected static route: string = ''
  protected static config: AxiosRequestConfig = {
    // todo: can this will need to be defined by the server itself
    // https://github.com/PrefectHQ/orion/issues/667
    baseURL: `http://localhost:4200${this.route}`,
  }
  protected static instance: AxiosInstance = axios.create(this.config)

  protected static request<T = any, R = AxiosResponse<T>>(config: AxiosRequestConfig): Promise<R> {
    return this.instance.request(config)
  }

  protected static get<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.get(url, config)
  }

  protected static delete<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.delete(url, config)
  }

  protected static head<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.head(url, config)
  }

  protected static options<T = any, R = AxiosResponse<T>>(url: string, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.options(url, config)
  }

  protected static post<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.post(url, data, config)
  }

  protected static put<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.put(url, data, config)
  }

  protected static patch<T = any, R = AxiosResponse<T>>(url: string, data?: any, config?: AxiosRequestConfig): Promise<R> {
    return this.instance.patch(url, data, config)
  }
}
