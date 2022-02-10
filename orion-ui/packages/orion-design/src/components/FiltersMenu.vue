<template>
  <div class="filters-menu">
    <div class="filters-menu__filters">
      <template v-for="(filter, index) in tempFilters" :key="filter.id">
        <FilterBuilder :filter="filter" dismissable expanded @update:filter="updateFilter(index, $event)" @dismiss="removeFilter(index)" />
      </template>
    </div>

    <div class="filters-menu__footer">
      <!-- not adding icon for now because the size is messed up -->
      <!-- saving search tips for later -->
      <!--
        <m-button miter class="mr-auto">
        Search Tips
        </m-button>
      -->
      <m-button flat miter class="text--primary ml-auto" @click="clear">
        Clear All
      </m-button>
      <m-button miter @click="cancel">
        Cancel
      </m-button>
      <m-button color="primary" miter @click="apply">
        Apply Filters
      </m-button>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { reactive, watch } from 'vue'
  import { useFiltersStore } from '../stores/filters'
  import { Filter } from '../types/filters'
  import { isCompleteFilter, isFilter } from '../utilities/filters'
  import FilterBuilder from './FilterBuilder.vue'

  const emit = defineEmits<{
    (event: 'close'): void,
  }>()

  const filters = useFiltersStore()

  const tempFilters: Partial<Filter>[] = reactive([...filters.all])

  watch(tempFilters, () => {
    if (tempFilters.every(filter => isFilter(filter))) {
      tempFilters.push({})
    }
  }, { immediate: true })

  function updateFilter(index: number, filter: Partial<Filter>): void {
    tempFilters[index] = filter
  }

  function removeFilter(index: number): void {
    tempFilters.splice(index, 1)
  }

  function clear(): void {
    tempFilters.splice(0)
  }

  function cancel(): void {
    emit('close')
  }

  function apply(): void {
    // currently just ignore non complete filters
    // probably will want to let the user know what's happening some how
    const completeFilters = tempFilters.filter(isCompleteFilter)

    filters.replaceAll(completeFilters)

    emit('close')
  }
</script>

<style lang="scss" scoped>
.filters-menu {
  background-color: #F4F5F7;
}

.filters-menu__filters {
  display: grid;
  gap: var(--m-1);
  padding: var(--p-2);
}

.filters-menu__footer {
  border-top: 1px solid #E8E8E8;
  background-color: #fff;
  padding: var(--p-1);
  display: flex;
  align-items: center;
  gap: var(--m-1);
}
</style>