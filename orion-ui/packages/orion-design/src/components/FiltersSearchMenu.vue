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

    <transition-group name="filters-search-menu-transition">
      <template v-if="loading">
        <m-loader key="loader" :loading="true" class="filters-search-menu__loader" />
      </template>

      <template v-else-if="empty">
        <p key="empty" class="filters-search-menu__empty">
          Click the <i class="pi pi-star-line" /> icon to save a search and it will show here.
        </p>
      </template>
    </transition-group>
  </div>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/miter-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { FilterUrlService } from '@/services/FilterUrlService'
  import { searchApiKey } from '@/services/SearchApi'
  import { Filter } from '@/types/filters'
  import { inject } from '@/utilities/inject'

  const emit = defineEmits<{
    (event: 'close'): void,
  }>()

  const searchApi = inject(searchApiKey)
  const subscription = useSubscription(searchApi.getSearches)
  const filters = computed(() => subscription.response ?? [])
  const empty = computed(() => filters.value.length === 0)
  const loading = computed(() => subscription.loading)
  const filterUrlService = new FilterUrlService(useRouter())

  function apply(filters: Required<Filter>[]): void {
    filterUrlService.replaceAll(filters)
    emit('close')
  }

  function remove(id: string): void {
    searchApi.deleteSearch(id)
      .then(() => {
        showToast('Search removed', 'success')
      })
      .catch(error => {
        showToast('Error removing search', 'error')
        console.error(error)
      })
      .finally(() => {
        subscription.refresh()
      })
  }
</script>

<style lang="scss">
.filters-search-menu {
  background: #FFFFFF;
  border-radius: 4px;
  overflow: hidden;
  max-height: 50vh;
  position: relative;
  min-height: 150px;
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

.filters-search-menu__empty,
.filters-search-menu__loader {
  position: absolute !important; // m-loader is scoped...
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.filters-search-menu__empty {
  vertical-align: middle;
  text-align: center;
  width: 100%;
}

.filters-search-menu__loader {
  --loader-size: 36px;
  margin: var(--m-2) auto;
}

.filters-search-menu-transition-enter-active,
.filters-search-menu-transition-leave-active {
  transition: opacity 0.5s ease;
}
.filters-search-menu-transition-enter-from,
.filters-search-menu-transition-leave-to {
  opacity: 0;
}
</style>