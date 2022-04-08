<template>
  <m-card class="filters-menu" background-color="#F4F5F7">
    <template #header>
      <div class="filters-menu__header">
        <p class="filters-menu__title">
          <i class="filters-save-menu__icon pi pi-filter-3-line" />
          Filters
        </p>
        <m-icon-button
          icon="pi-close-line"
          class="filters-menu__close"
          width="34px"
          height="34px"
          flat
          @click="emit('close')"
        />
      </div>
    </template>

    <div class="filters-menu__filters">
      <template v-for="(filter, index) in tempFilters" :key="filter.id">
        <FilterBuilder :filter="filter" dismissible expanded @update:filter="updateFilter(index, $event)" @dismiss="removeFilter(index)" />
      </template>
    </div>

    <template #actions>
      <div class="filters-menu__footer">
        <!-- not adding icon for now because the size is messed up -->
        <!-- saving search tips for later -->
        <!--
          <m-button miter class="mr-auto">
          Search Tips
          </m-button>
        -->
        <template v-if="tempFilters.length > 1">
          <m-button flat miter class="text--primary" @click="clear">
            Clear All
          </m-button>
        </template>
        <m-button miter class="" @click="cancel">
          Cancel
        </m-button>
        <m-button color="primary" miter @click="apply">
          Apply Filters
        </m-button>
      </div>
    </template>
  </m-card>
</template>

<script lang="ts" setup>
  import { reactive, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import FilterBuilder from '@/components/FilterBuilder.vue'
  import { FilterUrlService } from '@/services/FilterUrlService'
  import { useFiltersStore } from '@/stores/filters'
  import { Filter } from '@/types/filters'
  import { isCompleteFilter, isFilter } from '@/utilities/filters'
  import { clone } from '@/utilities/object'

  const emit = defineEmits<{
    (event: 'close'): void,
  }>()

  const filters = useFiltersStore()
  const router = useRouter()

  const tempFilters: Partial<Filter>[] = reactive(clone(filters.all))

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
    const service = new FilterUrlService(router)
    // currently just ignore non complete filters
    // probably will want to let the user know what's happening some how
    const completeFilters = tempFilters.filter(isCompleteFilter)

    service.replaceAll(completeFilters)

    emit('close')
  }
</script>

<style lang="scss">
@use 'sass:map';

.filters-menu {
  background-color: #F4F5F7;
}

.filters-menu__header {
  padding: var(--p-2);
  background-color: #fff;
  display: flex;

  @media (min-width: map.get($breakpoints, 'md')) {
    display: none;
  }
}

.filters-menu__title {
  margin: 0;
  font-weight: 600;
  font-size: 18px;
  letter-spacing: .24px;
  line-height: 22px;
  display: flex;
  align-items: center;
  margin-left: auto;

  @media (min-width: map.get($breakpoints, 'md')) {
    margin-left: 0;
  }
}

.filters-menu__icon {
  margin-right: var(--m-1);
  color: var(--grey-80);

  @media (min-width: map.get($breakpoints, 'md')) {
    display: none;
  }
}

.filters-menu__close {
  margin-left: auto;

  @media (min-width: map.get($breakpoints, 'md')) {
    display: none;
  }
}

.filters-menu__filters {
  display: grid;
  gap: var(--m-1);
  padding: var(--p-2);
  max-height: 85vh;
}

.filters-menu__footer {
  border-top: 1px solid #E8E8E8;
  background-color: #fff;
  padding: var(--p-1);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--m-1);
}
</style>