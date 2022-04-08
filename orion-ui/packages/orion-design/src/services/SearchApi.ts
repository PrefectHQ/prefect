import { InjectionKey } from 'vue'
import { SavedSearchResponse } from '@/models/SavedSearchResponse'
import { Api, ApiRoute } from '@/services/Api'
import { Filter } from '@/types/filters'

export class SearchApi extends Api {

  protected route: ApiRoute = '/saved_searches'

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

  public getSearches(request?: { limit?: number, number?: number }): Promise<SavedSearchResponse[]> {
    return this.post<SavedSearchResponse[]>('/filter', request).then(response => response.data)
  }
}

export const searchApiKey: InjectionKey<SearchApi> = Symbol('searchApiKey')