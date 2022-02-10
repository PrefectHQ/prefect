<template>
  <div class="filters-search-menu">
    <p class="filters-search-menu__title">
      Saved Searches
    </p>
    <template v-for="filter in filters" :key="filter.id">
      <button type="button" class="filters-search-menu__filter" @click="apply(filter.filters)">
        <span class="filters-search-menu__filter-name">{{ filter.name }}</span>
        <m-icon-button flat class="filters-search-menu__filter-remove" icon="pi-delete-bin-line pi-sm" @click.stop="remove(filter.id)" />
      </button>
    </template>
    <m-loader :loading="loading" class="filters-search-menu__loader" />
    <template v-if="empty && !loading">
      <p class="filters-search-menu__empty">
        Click the <i class="pi pi-star-line" /> icon to save a search and it will show here.
      </p>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/miter-design'
  import { subscribe } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { searchApi } from '../services/SearchApi'
  import { useFiltersStore } from '../stores/filters'
  import { Filter } from '../types/filters'

  const filtersStore = useFiltersStore()

  const subscription = subscribe(searchApi.filter.bind(searchApi), [])
  const filters = computed(() => subscription.response.value ?? [])
  const empty = computed(() => filters.value.length === 0)
  const loading = computed(() => subscription.loading.value)

  function apply(filters: Required<Filter>[]): void {
    filtersStore.replaceAll(filters)
  }

  function remove(id: string): void {
    searchApi.deleteSearch(id)
      .then(() => {
        showToast('Search removed', 'success')
      })
      .catch(error => {
        showToast('error', 'Error removing search')
        console.error(error)
      })
      .finally(() => {
        subscription.refresh()
      })
  }
</script>

<style lang="scss" scoped>
.filters-search-menu {
  background: #FFFFFF;
  border-radius: 4px;
  overflow: hidden;
  max-height: 50vh;
  position: relative;
}

.filters-search-menu__title {
  font-weight: 600;
  font-size: 16px;
  line-height: 24px;
  margin: 0;
  padding: var(--p-1) var(--p-2);
  position: sticky;
  top: 0;
}

.filters-search-menu__filter {
  --icon-color: var(--grey-20);

  appearance: none;
  border: 0;
  background: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--p-1) var(--p-2);
  width: 100%;

  &:hover {
    --icon-color: var(--grey-40);
  }

  &:hover,
  &:focus {
    background-color: #FCFDFE;
    color: var(--primary);
  }

}

.filters-search-menu__filter-name {
  font-size: 16px;
  line-height: 24px;
}

// important necessary because of MIconButtons styles
.filters-search-menu__filter-remove {
  color: var(--icon-color) !important;

  &:hover {
    color: var(--error) !important;
  }
}

.filters-search-menu__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.filters-search-menu__loader {
  --loader-size: 36px;
  margin: var(--m-2) auto;
}
</style>