import { computed, Ref } from 'vue'
import { UnionFilters } from '@/services/Filter'
import { FiltersQueryService } from '@/services/FiltersQueryService'
import { useFiltersStore } from '@/stores/filters'

export function useFilterQuery(): Ref<UnionFilters> {
  const filtersStore = useFiltersStore()

  return computed<UnionFilters>(() => {
    return FiltersQueryService.query(filtersStore.all)
  })
}