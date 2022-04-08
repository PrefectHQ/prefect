import { defineStore } from 'pinia'
import { InjectionKey } from 'vue'
import { SimpleIdManager } from '@/services/SimpleIdManager'
import { Filter } from '@/types/filters'
import { toRecord } from '@/utilities/arrays'

export type FilterState = {
  id: number,
} & Required<Filter>

type FiltersState = {
  filters: Record<number, FilterState>,
}

const filtersIdManager = new SimpleIdManager()

export const useFiltersStore = defineStore('filters', {
  state: (): FiltersState => ({
    filters: {},
  }),
  actions: {
    add(filter: Required<Filter>): FilterState {
      const id = filtersIdManager.get()
      const filterState = {
        ...filter,
        id,
      }

      this.filters[id] = filterState

      return filterState
    },
    remove(filter: FilterState): void {
      delete this.filters[filter.id]
    },
    removeAll(): void {
      this.filters = {}
    },
    replaceAll(filters: Required<Filter>[]): void {
      const filtersState = filters.map(filter => ({
        ...filter,
        id: filtersIdManager.get(),
      }))

      this.filters = toRecord(filtersState, 'id')
    },
  },
  getters: {
    all: (state) => Object.values(state.filters),
  },
})

export const filterStoreKey: InjectionKey<ReturnType<typeof useFiltersStore>> = Symbol('filterStoreKey')