import { useFiltersStore, RouteGuard } from '@prefecthq/orion-design'
import { FilterService } from '@prefecthq/orion-design/services'
import { asArray, isString } from '@prefecthq/orion-design/utilities'
import { RouteLocationNormalized, Router } from 'vue-router'

export class GlobalLoadFiltersFromRoute implements RouteGuard {
  
  public before(to: RouteLocationNormalized, from: RouteLocationNormalized): void {
    if (JSON.stringify(to.query.filter) !== JSON.stringify(from.query.filter)) {
      const filterStrings = asArray(to.query.filter).filter(isString)
      const parsedFilters = FilterService.parse(filterStrings)
      const filtersStore = useFiltersStore()

      filtersStore.replaceAll(parsedFilters)
    }
  }

}