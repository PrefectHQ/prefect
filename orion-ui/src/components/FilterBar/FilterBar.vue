<template>
  <div
    class="bar-wrapper d-flex font--secondary"
    :class="{ detached: detached, active: overlay }"
    @keyup.esc="closeOverlay"
  >
    <div class="bar" :class="{ 'menu-opened': showFilterMenu }">
      <FilterSearch @focused="openSearchMenu">
        <TagGroup
          :tags="filters"
          :clearable="false && filtersApplied"
          @click="openFilterMenu"
          @remove="removeFilter"
        />

        <a
          v-breakpoints="'sm'"
          v-if="filtersApplied && filters.length"
          class="
            text--primary text-decoration-none
            font--secondary
            caption
            nowrap
            ml-1
          "
          @click="clearFilters"
        >
          Clear all
        </a>
      </FilterSearch>

      <div class="saved-searches-container">
        <button
          class="filter-button saved-searches text--grey-80 px-2"
          :class="{ active: showSaveSearch }"
          @click="showSaveSearch ? closeSaveSearchMenu() : openSaveSearchMenu()"
        >
          <i class="pi pi-star-line" />
        </button>
      </div>

      <div class="filter-container">
        <button
          class="filter-button filters text--grey-80 px-2"
          :class="{ active: showFilterMenu }"
          @click="showFilterMenu ? closeFilterMenu() : openFilterMenu()"
        >
          <i class="pi pi-filter-3-line" />
          <span v-breakpoints="'sm'" class="ml-1">Filters</span>
        </button>
      </div>

      <teleport to="#app">
        <div class="observe" ref="observe" />
      </teleport>

      <teleport v-if="overlay" to=".application">
        <div class="overlay" @click="closeOverlay" />
      </teleport>

      <transition-group name="fade-slide" mode="out-in">
        <SearchMenu
          v-if="showSearchMenu"
          key="search-menu"
          class="search-menu"
          @close="closeSearchMenu"
        />

        <SaveSearchMenu
          v-if="showSaveSearch"
          key="save-search-menu"
          class="save-search-menu"
          @close="closeSaveSearchMenu"
        />

        <FilterMenu
          v-else-if="showFilterMenu"
          key="filter-menu"
          class="filter-menu"
          @close="closeFilterMenu"
        />
      </transition-group>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import FilterMenu from './FilterMenu.vue'
import FilterSearch from './FilterSearch.vue'
import SearchMenu from './SearchMenu.vue'
import SaveSearchMenu from './SaveSearchMenu.vue'
import { parseFilters, FilterObject } from './util'
import { initialGlobalFilterState } from '@/store'
import TagGroup from './TagGroup.vue'

const store = useStore()
const route = useRoute()

const showFilterMenu = ref<boolean>(false)
const showSearchMenu = ref<boolean>(false)
const showSaveSearch = ref<boolean>(false)
const showOverlay = ref<boolean>(false)

const closeSaveSearchMenu = () => {
  showSaveSearch.value = false
}

const openSaveSearchMenu = () => {
  showSearchMenu.value = false
  showFilterMenu.value = false
  showSaveSearch.value = true
}

const closeFilterMenu = () => {
  showFilterMenu.value = false
}

const openFilterMenu = () => {
  showSaveSearch.value = false
  showSearchMenu.value = false
  showFilterMenu.value = true
}

const closeSearchMenu = () => {
  showSearchMenu.value = false
}

const openSearchMenu = () => {
  showFilterMenu.value = false
  showSaveSearch.value = false
  showSearchMenu.value = true
}

const closeOverlay = () => {
  showFilterMenu.value = false
  showSaveSearch.value = false
  showSearchMenu.value = false
  showOverlay.value = false

  if (document.activeElement) {
    ;(document.activeElement as HTMLElement).blur()
  }
}

const removeFilter = (filter: FilterObject): void => {
  console.log(filter)
}

const filters = computed<FilterObject[]>(() => {
  return parseFilters(store.getters.globalFilter)
})

/**
 * This section is for performantly handling intersection of the filter bar
 */

const detached: Ref<boolean> = ref(false)

const handleEmit = ([entry]: IntersectionObserverEntry[]) =>
  (detached.value = !entry.isIntersecting)

const observe = ref<Element>()

let observer: IntersectionObserver

const createIntersectionObserver = (margin: string) => {
  if (observe.value) observer?.unobserve(observe.value)

  const options = {
    rootMargin: margin,
    threshold: [0.1, 1]
  }

  observer = new IntersectionObserver(handleEmit, options)
  if (observe.value) observer.observe(observe.value)
}

const overlay = computed(() => {
  return (
    showFilterMenu.value ||
    showSaveSearch.value ||
    showOverlay.value ||
    showSearchMenu.value
  )
})

const filtersApplied = computed(() => {
  return (
    JSON.stringify(initialGlobalFilterState) !==
    JSON.stringify(store.getters.globalFilter)
  )
})

const clearFilters = () => {
  store.commit('resetFilters')
}

onMounted(() => {
  createIntersectionObserver('0px')
})

onBeforeUnmount(() => {
  if (observe.value) observer?.unobserve(observe.value)
})

watch(route, () => {
  if (route.name == 'Dashboard') {
    if (observe.value) observer?.observe(observe.value)
  } else {
    if (observe.value) observer?.unobserve(observe.value)
    detached.value = true
  }
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-bar.scss';
</style>
