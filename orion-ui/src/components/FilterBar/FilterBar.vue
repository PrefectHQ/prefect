<template>
  <div class="bar d-flex font--secondary" :class="{ detached: detached }">
    <div class="object-container">
      <button
        class="filter-button objects text--grey-80"
        @click="showObjectMenu = !showObjectMenu"
      >
        <span v-breakpoints="'sm'" class="mr-1">Flow Runs</span>
        <i class="pi pi-arrow-drop-down-fill" />
      </button>

      <ObjectMenu
        v-if="showObjectMenu"
        v-model="object"
        class="filter-menu"
        @close="showObjectMenu = false"
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

    <div class="filter-container">
      <button
        class="filter-button filters text--grey-80"
        @click="showOverlay = !showOverlay"
      >
        <i class="pi pi-filter-3-line" />
        <span v-breakpoints="'sm'" class="ml-1">Filters</span>
      </button>
    </div>

    <teleport to="#app">
      <div class="observe" ref="observe" />
    </teleport>

    <teleport to=".application">
      <div v-show="showOverlay" class="overlay" @click="showOverlay = false" />
    </teleport>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted } from 'vue'
import ObjectMenu from './ObjectMenu.vue'

const search = ref<string>('')

const showObjectMenu = ref<boolean>(false)
const showOverlay = ref<boolean>(false)

const object = ref<string>('flows')

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

onMounted(() => {
  createIntersectionObserver('0px')
})

onBeforeUnmount(() => {
  if (observe.value) observer?.unobserve(observe.value)
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/filter-bar.scss';
</style>
