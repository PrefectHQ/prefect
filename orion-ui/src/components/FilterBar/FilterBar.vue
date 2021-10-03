<template>
  <div
    class="bar-wrapper d-flex font--secondary"
    :class="{ detached: detached }"
  >
    <div class="bar" :class="{ 'menu-opened': showFilterMenu }">
      <div class="object-container">
        <button
          class="filter-button objects text--grey-80 pl-3 pr-1"
          @click="toggleObjectMenu"
        >
          <span v-breakpoints="'sm'" v-if="selectedObject" class="mr-1 object">
            {{ selectedObject }}
          </span>
          <i class="pi pi-arrow-drop-down-fill" />
        </button>

        <ObjectMenu
          v-if="showObjectMenu"
          class="object-menu"
          @close="toggleObjectMenu"
        />
      </div>

      <div
        class="
          search-input
          px-2
          flex-grow-1 flex-shrink-0
          d-flex
          align-center
          font--primary
        "
      >
        <i class="pi pi-search-line mr-1" />
        <input v-model="search" class="flex-grow-1" placeholder="Search..." />
      </div>

      <div class="saved-searches-container">
        <button
          class="filter-button saved-searches text--grey-80 px-2"
          @click="toggleSavedSearchesMenu"
        >
          <i class="pi pi-star-line" />
        </button>
      </div>

      <div class="filter-container">
        <button
          class="filter-button filters text--grey-80 px-2"
          @click="toggleFilterMenu"
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

      <FilterMenu
        v-if="showFilterMenu"
        class="filter-menu"
        @close="toggleObjectMenu"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import ObjectMenu from './ObjectMenu.vue'
import FilterMenu from './FilterMenu.vue'

const store = useStore()
const route = useRoute()

const search = ref<string>('')

const showObjectMenu = ref<boolean>(false)
const showFilterMenu = ref<boolean>(false)
const showSavedSearchesMenu = ref<boolean>(false)
const showOverlay = ref<boolean>(false)

const selectedObject = computed(() => {
  return store.getters.globalFilter.object.replace('_', ' ')
})

const toggleObjectMenu = () => {
  showObjectMenu.value = !showObjectMenu.value
}

const toggleSavedSearchesMenu = () => {
  showSavedSearchesMenu.value = !showSavedSearchesMenu.value
}

const toggleFilterMenu = () => {
  showFilterMenu.value = !showFilterMenu.value
}

const closeOverlay = () => {
  showObjectMenu.value = false
  showFilterMenu.value = false
  showSavedSearchesMenu.value = false
  showOverlay.value = false
}

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
    showObjectMenu.value ||
    showFilterMenu.value ||
    showSavedSearchesMenu.value ||
    showOverlay.value
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
