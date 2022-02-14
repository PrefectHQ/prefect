import { FilterService } from "@/../packages/orion-design/src/services/FilterService";
import { useFiltersStore } from "@/../packages/orion-design/src/stores/filters";
import { RouteLocationNormalized, Router } from "vue-router";
import { RouteGuard } from "./RouteGuard";
import { asArray } from "@/../packages/orion-design/src/utilities/arrays";
import { isString } from "@/../packages/orion-design/src/utilities/strings";

export class GlobalLoadFiltersFromRoute implements RouteGuard {
  private router: Router

  public constructor(router: Router) {
    this.router = router
  }
  
  public before(to: RouteLocationNormalized, from: RouteLocationNormalized): void {
    if(JSON.stringify(to.query.filter) !== JSON.stringify(from.query.filter)) {
      const filterStrings = asArray(to.query.filter).filter(isString)
      const parsedFilters = FilterService.parse(filterStrings)
      const filtersStore = useFiltersStore()

      filtersStore.replaceAll(parsedFilters)
    }
  }
  
}