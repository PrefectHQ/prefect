import { defineStore } from 'pinia'
import { SimpleIdManager } from '../services/SimpleIdManager'
import { Filter } from '../types/filters'
import { toRecord } from '../utilities/arrays'

type FilterState = {
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