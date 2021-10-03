<template>
  <div class="bar d-flex font--secondary" :class="{ detached: detached }">
    <button class="filter-button objects">
      <span v-breakpoints="'sm'" class="mr-1">Flow Runs</span>
      <i class="pi pi-arrow-drop-down-fill" />
    </button>

    <div class="search-input px-2 flex-grow-1 d-flex align-center">
      <i class="pi pi-search-line mr-1" />
      <input v-model="search" class="flex-grow-1" placeholder="Search..." />
    </div>

    <button class="filter-button filters">
      <i class="pi pi-filter-3-line" />
      <span v-breakpoints="'sm'" class="ml-1">Filters</span>
    </button>

    <teleport to="#app">
      <div class="observe" ref="observe" />
    </teleport>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted } from 'vue'

const search = ref<string>('')

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

<style lang="scss">
@use '@/styles/components/filter-bar.scss';
</style>
