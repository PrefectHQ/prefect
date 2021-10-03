<template>
  <div class="bar d-flex font--secondary" :class="{ detached: detached }">
    <div class="object-container">
      <button
        class="filter-button objects text--grey-80"
        @click="toggleObjectMenu"
      >
        <span v-breakpoints="'sm'" v-if="selectedObject" class="mr-1">
          {{ selectedObject.label }}
        </span>
        <i class="pi pi-arrow-drop-down-fill" />
      </button>

      <ObjectMenu
        v-if="showObjectMenu"
        v-model="obj"
        :options="objectOptions"
        class="filter-menu"
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

    <div class="filter-container">
      <button
        class="filter-button filters text--grey-80"
        @click="toggleFilterMenu"
      >
        <i class="pi pi-filter-3-line" />
        <span v-breakpoints="'sm'" class="ml-1">Filters</span>
      </button>
    </div>

    <teleport to="#app">
      <div class="observe" ref="observe" />
    </teleport>

    <teleport v-if="showOverlay" to=".application">
      <div class="overlay" @click="closeOverlay" />
    </teleport>
  </div>
</template>

<script lang="ts" setup>
import { ref, Ref, onBeforeUnmount, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import ObjectMenu from './ObjectMenu.vue'

const route = useRoute()

type objectOption = { label: string; value: string }
const objectOptions: objectOption[] = [
  { label: 'Flows', value: 'flows' },
  { label: 'Deployments', value: 'deployments' },
  { label: 'Flow Runs', value: 'flow_runs' },
  { label: 'Task Runs', value: 'task_runs' }
]

const search = ref<string>('')

const showObjectMenu = ref<boolean>(false)
const showFilterMenu = ref<boolean>(false)
const showOverlay = ref<boolean>(false)

const obj = ref<string>('flows')

const selectedObject = computed(() => {
  return objectOptions.find((o) => o.value == obj.value)
})

const toggleObjectMenu = () => {
  showObjectMenu.value = !showObjectMenu.value
  showOverlay.value = !showOverlay.value
}

const toggleFilterMenu = () => {
  showFilterMenu.value = !showFilterMenu.value
  showOverlay.value = !showOverlay.value
}

const closeOverlay = () => {
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
