<template>
  <div class="filters-search">
    <template v-if="!hasFilters">
      <i class="pi pi-search-line" />
    </template>
    <template v-else>
      <template v-if="filters.length <= 3 && media.sm">
        <FilterTags :filters="filters" class="filters-search__tags" :dismissible="dismissable" @dismiss="dismiss" @click.stop />
      </template>
      <template v-else>
        <DismissibleTag :label="filtersLabel" :dismissible="dismissable" @dismiss="dismissAll" @click.stop />
      </template>
    </template>
    <input
      v-model="term"
      class="filters-search__input"
      type="text"
      :placeholder="placeholderText"
      @keypress.prevent.enter="add"
      @keypress.prevent.tab="add"
    >
    <template v-if="term.length">
      <button type="button" class="filters-search__clear" @click="clear">
        <i class="pi pi-sm pi-close-circle-fill" />
      </button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import {  useRouter } from 'vue-router'
  import DismissibleTag from '@/components/DismissibleTag.vue'
  import FilterTags from '@/components/FilterTags.vue'
  import { FilterPrefixError } from '@/models/FilterPrefixError'
  import { FilterService } from '@/services/FilterService'
  import { FilterUrlService } from '@/services/FilterUrlService'
  import { useFiltersStore, FilterState } from '@/stores/filters'
  import { media } from '@/utilities/media'
  import { toPluralString } from '@/utilities/strings'

  interface Props {
  dismissable?: boolean
  showPlaceholder?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  dismissable: true,
  showPlaceholder: true
})

  

  const filtersStore = useFiltersStore()
  const filterUrlService = new FilterUrlService(useRouter())
  const term = ref('')
  const filters = computed(() => filtersStore.all)
  const filtersLabel = computed(() => `${filters.value.length} ${toPluralString('filter', filters.value.length)}`)
  const hasFilters = computed(() => filters.value.length > 0)
  const placeholderText = computed(()=> props.showPlaceholder ? 'Search...' : '')
  function add(): void {
    if (term.value == '') {
      return
    }

    try {
      const filter = FilterService.parse(term.value)

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

  function dismissAll(): void {
    filterUrlService.removeAll()
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
  appearance: none;
  cursor: pointer;
  border: 0;
  background: none;
  color: var(--grey-40);

  &:hover {
    color: var(--grey-80);
  }
}
</style>