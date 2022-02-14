import { Filter } from '../types/filters'
import { Api } from './Api'

export type SavedSearchRequest = {
  name: string,
  filters: Required<Filter>[],
}

export type SavedSearchResponse = {
  id: string,
  created: string,
  updated: string,
  name: string,
  filters: Required<Filter>[],
}

export class SearchApi extends Api {

  protected route: string = '/api/saved_searches'

  public createSearch(name: string, filters: Filter[]): Promise<SavedSearchResponse> {
    return this.put<SavedSearchResponse>('/', {
      name,
      filters,
    }).then(response => response.data)
  }

  public getSearch(id: string): Promise<SavedSearchResponse> {
    return this.put<SavedSearchResponse>(`/${id}`).then(response => response.data)
  }

  public deleteSearch(id: string): Promise<void> {
    return this.delete(`/${id}`)
  }

  public filter(request?: { limit?: number, number?: number }): Promise<SavedSearchResponse[]> {
    return this.post<SavedSearchResponse[]>('/filter', request).then(response => response.data)
  }
}

export const searchApi = new SearchApi()
