<template>
  <div
    class="bar-wrapper d-flex font--secondary"
    :class="{ detached: detached }"
  >
    <div class="bar" :class="{ 'menu-opened': showFilterMenu }">
      <FilterSearch @focused="openSearchMenu">
        <div
          class="filter-tag mr-1 font--secondary caption"
          v-for="(filter, i) in filters"
          :key="i"
          tabindex="0"
          @click="removeFilter(filter)"
        >
          <div class="px-1 py--half d-flex align-center">
            <i class="pi pi-xs mr--half" :class="filter.icon" />
            {{ filter.objectLabel }}

            <button class="ml-1">
              <i class="pi pi-xs pi-close-circle-fill" />
            </button>
          </div>
        </div>

        <a
          v-if="filters.length"
          class="text--primary text-decoration-none font--secondary caption"
        >
          Clear all
        </a>
      </FilterSearch>

      <div class="saved-searches-container">
        <button
          class="filter-button saved-searches text--grey-80 px-2"
          @click="
            showSavedSearchesMenu
              ? closeSavedSearchesMenu()
              : openSavedSearchesMenu()
          "
        >
          <i class="pi pi-star-line" />
        </button>
      </div>

      <div class="filter-container">
        <button
          class="filter-button filters text--grey-80 px-2"
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

      <SearchMenu
        v-if="showSearchMenu"
        class="search-menu"
        @close="closeSearchMenu"
      />

      <FilterMenu
        v-if="showFilterMenu"
        class="filter-menu"
        @close="closeFilterMenu"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { GlobalFilter } from '@/typings/global'
import { ref, Ref, onBeforeUnmount, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import FilterMenu from './FilterMenu.vue'
import FilterSearch from './FilterSearch.vue'
import SearchMenu from './SearchMenu.vue'

const store = useStore()
const route = useRoute()

const showFilterMenu = ref<boolean>(false)
const showSearchMenu = ref<boolean>(false)
const showSavedSearchesMenu = ref<boolean>(false)
const showOverlay = ref<boolean>(false)

const closeSavedSearchesMenu = () => {
  showSavedSearchesMenu.value.value = false
}

const openSavedSearchesMenu = () => {
  showSearchMenu.value = false
  showFilterMenu.value = false
  showSavedSearchesMenu.value = true
}

const closeFilterMenu = () => {
  showFilterMenu.value = false
}

const openFilterMenu = () => {
  showSavedSearchesMenu.value = false
  showSearchMenu.value = false
  showFilterMenu.value = true
}

const closeSearchMenu = () => {
  showSearchMenu.value = false
}

const openSearchMenu = () => {
  showFilterMenu.value = false
  showSavedSearchesMenu.value = false
  showSearchMenu.value = true
}

const closeOverlay = () => {
  showFilterMenu.value = false
  showSavedSearchesMenu.value = false
  showSearchMenu.value = false
  showOverlay.value = false
}

const removeFilter = (filter: FilterObject): void => {
  console.log(filter)
}

type FilterObject = {
  objectKey: string
  objectLabel: string
  filterKey: string
  filterValue: string
  icon: string
}

const filters = computed<FilterObject[]>(() => {
  const arr: any[] = []
  const gf: GlobalFilter = store.getters.globalFilter
  const keys = Object.keys(gf)
  keys.forEach((key) => {
    Object.entries(gf[key as keyof GlobalFilter]).forEach(
      ([k, v]: [string, any]) => {
        if (k == 'states' && Array.isArray(v)) {
          let filterValue

          if (v.length == 6) filterValue = 'All'
          else if (v.length == 0) filterValue = 'None'
          else filterValue = v.join(', ')

          arr.push({
            objectKey: key,
            objectLabel: v.length == 1 ? 'State' : 'States',
            filterKey: k,
            filterValue: filterValue,
            icon: 'pi-focus-3-line'
          })
        } else if (k == 'timeframe') {
          if (v.from) {
            let filterValue
            if (v.from.timestamp)
              filterValue = new Date(v.from.timestamp).toLocaleString()
            else if (v.from.value && v.from.unit)
              filterValue = `${v.from.value}${v.from.unit.slice(0, 1)}`

            arr.push({
              objectKey: key,
              objectLabel: `Past ${filterValue}`,
              filterKey: k,
              filterValue: filterValue,
              icon: 'pi-scheduled'
            })
          }
          if (v.to) {
            let filterValue
            if (v.to.timestamp)
              filterValue = new Date(v.to.timestamp).toLocaleString()
            else if (v.to.value && v.to.unit)
              filterValue = `${v.to.value}${v.to.unit.slice(0, 1)}`

            arr.push({
              objectKey: key,
              objectLabel: `Next ${filterValue}`,
              filterKey: k,
              filterValue: filterValue,
              icon: 'pi-scheduled'
            })
          }
        } else {
          arr.push({
            objectKey: key,
            objectLabel: `${key.replace('_', ' ')}: ${v}`,
            filterKey: k,
            filterValue: v,
            icon: 'pi-search-line'
          })
        }
      }
    )
  })
  return arr
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
    showSavedSearchesMenu.value ||
    showOverlay.value ||
    showSearchMenu.value
  )
})

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
@use '@/styles/components/filter-bar.scss';
</style>
