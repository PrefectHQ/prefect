<template>
  <div class="filters-search">
    <template v-if="!hasFilters">
      <i class="pi pi-search-line" />
    </template>
    <template v-else>
      <FilterTags v-bind="{ filters, dismissible }" class="filters-search__tags" auto-hide @dismiss="dismiss" @click.stop />
    </template>
    <input
      v-model="term"
      class="filters-search__input"
      type="text"
      :placeholder="placeholder"
      @keypress.prevent.enter="add"
      @keypress.prevent.tab="add"
    >
    <button type="button" class="filters-search__clear" :class="classes.clear" @click="clear">
      <i class="pi pi-sm pi-close-circle-fill" />
    </button>
  </div>
</template>

<script lang="ts" setup>
  import { computed, inject, ref, withDefaults } from 'vue'
  import {  useRouter } from 'vue-router'
  import FilterTags from '@/components/FilterTags.vue'
  import { FilterPrefixError } from '@/models/FilterPrefixError'
  import { filtersDefaultObjectKey, FilterService } from '@/services/FilterService'
  import { FilterUrlService } from '@/services/FilterUrlService'
  import { useFiltersStore, FilterState } from '@/stores/filters'

  interface Props {
    dismissible?: boolean,
    placeholder?: string,
  }

  withDefaults(defineProps<Props>(), {
    placeholder: 'Search...',
  })


  const filtersStore = useFiltersStore()
  const filterUrlService = new FilterUrlService(useRouter())
  const term = ref('')
  const filters = computed(() => filtersStore.all)
  const hasFilters = computed(() => filters.value.length > 0)
  const defaultObject = inject(filtersDefaultObjectKey, 'flow_run')


  const classes = computed(() => ({
    clear: {
      'filters-search__clear--visible': term.value.length,
    },
  }))

  function add(): void {
    if (term.value == '') {
      return
    }

    try {
      const filter = FilterService.parse(term.value, defaultObject)

      filterUrlService.add(filter)
      clear()
    } catch (error) {
      if (error instanceof FilterPrefixError && !term.value.includes(':')) {
        term.value = `f:${term.value}`

        return add()
      }

      console.error(error)
    }
  }

  function dismiss(filter: FilterState): void {
    filterUrlService.remove(filter)
  }

  function clear(): void {
    term.value = ''
  }
</script>

<style lang="scss">
@use 'sass:map';

.filters-search {
  display: flex;
  align-items: center;
  background-color: #fff;
  padding: var(--p-1) var(--p-2);
  gap: var(--p-1);
  overflow: hidden;
}

.filters-search__tags {
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
}

.filters-search__input {
  appearance: none;
  border: 0;
  background-color: transparent;
  font-size: 16px;
  flex-grow: 1;
  min-width: 100px;
  min-height: 30px;
  align-self: stretch;
  width: 100px;

  @media (min-width: map.get($breakpoints, 'sm')) {
    width: auto;
  }

  &::placeholder {
    color: var(--grey-40);
  }

  &:focus {
    outline: 0;
  }
}

.filters-search__clear {
  opacity: 0;
  appearance: none;
  cursor: pointer;
  border: 0;
  background: none;
  color: var(--grey-40);

  &:hover {
    color: var(--grey-80);
  }
}

.filters-search__clear--visible {
  opacity: 1;
}
</style>