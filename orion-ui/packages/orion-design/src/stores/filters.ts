import { defineStore } from 'pinia'
import { SimpleIdManager } from '../services/SimpleIdManager'
import { Filter } from '../types/filters'

type FilterState = {
  id: number,
} & Filter

type FiltersState = {
  filters: Record<number, FilterState>,
}

const filtersIdManager = new SimpleIdManager()

export const useFiltersStore = defineStore('filters', {
  state: (): FiltersState => ({
    filters: {},
  }),
  actions: {
    add(filter: Filter): FilterState {
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
    replaceAll(filters: Filter[]): void {
      const filtersState = filters.map(filter => ({
        ...filter,
        id: filtersIdManager.get(),
      }))

      this.filters = filtersState
    },
  },
  getters: {
    all: (state) => Object.values(state.filters),
  },
})