<template>
  <div class="filters-builder">
    <template v-for="(filter, index) in tempFilters" :key="filter.id">
      <!-- eslint-disable-next-line vue/valid-v-model -->
      <FilterBuilder :filter="filter" dismissable @update:filter="updateFilter(index, $event)" @dismiss="removeFilter(index)" />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { reactive, watch } from 'vue'
  import { useFiltersStore } from '../stores/filters'
  import { Filter } from '../types/filters'
  import { isFilter } from '../utilities/filters'
  import FilterBuilder from './FilterBuilder.vue'

  const filters = useFiltersStore()

  const tempFilters: Partial<Filter>[] = reactive(filters.all)

  function updateFilter(index: number, filter: Partial<Filter>): void {
    tempFilters[index] = filter
  }

  function removeFilter(index: number): void {
    tempFilters.splice(index, 1)
  }

  watch(tempFilters, () => {
    if (tempFilters.every(filter => isFilter(filter))) {
      tempFilters.push({})
    }
  }, { immediate: true })
</script>

<style lang="scss" scoped>
.filters-builder {
  display: grid;
  gap: var(--m-1);
}
</style>