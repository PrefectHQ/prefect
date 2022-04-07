<template>
  <div class="filter-bar" :class="classes.root">
    <FiltersSearch class="filter-bar__search" :placeholder="placeholderText" :dismissible="!disabled" @click="show('search')" />

    <button type="button" class="filter-bar__button" :class="classes.saveButton" @click="toggle('save')">
      <i class="pi pi-star-line" />
    </button>

    <button type="button" class="filter-bar__button" :class="classes.filtersButton" @click="toggle('filters')">
      <i class="pi pi-filter-3-line" />
      <span v-if="media.sm" class="ml-1">Filters</span>
    </button>

    <teleport to="#app">
      <div ref="observe" class="filter-bar__observe" />
    </teleport>

    <teleport v-if="overlay" to="[data-teleport-target='app']">
      <div class="filter-bar__overlay" @click="close" />
    </teleport>

    <transition-group name="filter-bar-transition" mode="out-in">
      <template v-if="isOpen('search')">
        <div key="search" class="filter-bar__menu filter-bar__menu-search">
          <FiltersSearchMenu @close="toggle('search')" />
        </div>
      </template>

      <template v-if="isOpen('save')">
        <div key="save" class="filter-bar__menu filter-bar__menu--save">
          <FiltersSaveMenu class="filter-bar_menu-content" @close="close" />
        </div>
      </template>

      <template v-if="isOpen('filters')">
        <div key="filters" class="filter-bar__menu">
          <FiltersMenu class="filter-bar_menu-content" @close="close" />
        </div>
      </template>
    </transition-group>
  </div>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
  import FiltersMenu from '@/components/FiltersMenu.vue'
  import FiltersSaveMenu from '@/components/FiltersSaveMenu.vue'
  import FiltersSearch  from '@/components/FiltersSearch.vue'
  import FiltersSearchMenu from '@/components/FiltersSearchMenu.vue'
  import { FilterService } from '@/services/FilterService'
  import { searchApiKey } from '@/services/SearchApi'
  import { useFiltersStore } from '@/stores/filters'
  import { isSame } from '@/utilities/arrays'
  import { inject } from '@/utilities/inject'
  import { media } from '@/utilities/media'

  type Menu = 'none' | 'search' | 'save' | 'filters'

  const props = defineProps<{
    disabled?: boolean,
  }>()

  const menu = ref<Menu>('none')
  const detached = ref(false)
  const overlay = computed(() => menu.value !== 'none')
  const placeholderText = computed(()=> props.disabled ? '' : 'Search...')

  const filtersStore = useFiltersStore()
  const searchApi = inject(searchApiKey)!
  const searchesSubscription = useSubscription(searchApi.getSearches)
  const savedSearches = computed(() => searchesSubscription.response ?? [])

  const usingSavedSearch = computed(() => {
    const stringFilters = FilterService.stringify(filtersStore.all)

    return savedSearches.value.some(search => isSame(FilterService.stringify(search.filters), stringFilters))
  })

  const classes = computed(() => ({
    root: {
      'filter-bar--disabled': props.disabled,
      'filter-bar--detached': detached.value,
    },
    saveButton: {
      'filter-bar__button--open': isOpen('save'),
      'filter-bar__button--active': usingSavedSearch.value,
    },
    filtersButton: {
      'filter-bar__button--open': isOpen('filters'),
    },
  }))

  function isOpen(value: Menu): boolean {
    return menu.value === value
  }

  function show(value: Menu): void {
    menu.value = value
  }

  function toggle(value: Menu): void {
    if (isOpen(value)) {
      close()
    } else {
      show(value)
    }
  }

  function close(): void {
    menu.value = 'none'
    const activeElement = document.activeElement as HTMLElement
    activeElement.blur()
  }

  /**
   * This section is for performantly handling intersection of the filter bar
   */

  const handleEmit = ([entry]: IntersectionObserverEntry[]): boolean => {
    return detached.value = !entry.isIntersecting
  }

  const observe = ref<Element>()

  let observer: IntersectionObserver | null

  const createIntersectionObserver = (margin: string): void => {
    tryUnobserve()

    const options = {
      rootMargin: margin,
      threshold: [0.1, 1],
    }

    observer = new IntersectionObserver(handleEmit, options)

    tryObserve()
  }

  const tryObserve = (): void => {
    if (observe.value) {
      observer?.observe(observe.value)
    }
  }

  const tryUnobserve = (): void => {
    if (observe.value) {
      observer?.unobserve(observe.value)
    }
  }

  onMounted(() => {
    createIntersectionObserver('0px')
  })

  onBeforeUnmount(() => {
    if (observe.value) {
      observer?.unobserve(observe.value)
    }
  })
</script>

<style lang="scss">
.filter-bar {
  margin: var(--m-2) var(--m-4);
  position: sticky;
  top: 0;
  transition: all 150ms;
  left: 0;
  filter: $drop-shadow-sm;
  height: 62px;
  background: #fff;
  display: flex;
  align-items: stretch;
  z-index: 9;

  @media (max-width: 1024px) {
    margin: 0;
    border-radius: 0;
    z-index: 9;
  }

  @media (max-width: 640px) {
    z-index: 10;
  }
}

.filter-bar--detached {
    margin: 0;
    border-radius: 0;

  @media (max-width: 640px) {
    top: 62px;
  }
}

.filter-bar--disabled {
  pointer-events: none;
  cursor: default;

  &::after {
    position: absolute;
    content: '';
    display: block;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--grey-80);
    opacity: 0.1;
  }
}

.filter-bar__observe {
  position: absolute;
  height: 16px;
  left: 0;
  opacity: 0;
  top: 0;
  width: 100px;
}

.filter-bar__overlay {
  background-color: rgba(0, 0, 0, 0.1);
  // Note: this will only work in browsers that allow backdrop-filter, (so Chrome, Edge, and FF only if the experimental prop is enabled)
  backdrop-filter: blur(1px);
  height: 100%;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  z-index: 8;
}

.filter-bar__search {
  flex-grow: 1;
}

.filter-bar__button {
  appearance: none;
  border: 0;
  background: none;
  display: flex;
  align-items: center;
  padding: 0 var(--p-2);
  cursor: pointer;
  border-left: 1px solid var(--secondary-hover);
  font-family: var(--font-secondary);
  font-size: 14px;
  color: var(--grey-80);

  &:not(.filter-bar__button--open) {
    &:hover,
    &.active,
    &:focus {
      background-color: var(--grey-10);
    }
  }
}

.filter-bar__button--active {
  color: var(--primary);
}

.filter-bar__button--open {
  background-color: var(--primary);
  color: #fff;
}

.filter-bar__menu {
  position: absolute !important; // scoped styles in m-card
  border-radius: 0 0 4px 4px !important; // m-card
  left: 0;
  top: 100%;
  right: 0;
  z-index: 1;
  border-top: 1px solid var(--secondary-hover);
  overflow: hidden;
  display: grid;

  @media (max-width: 1024px) {
    left: 0;
    top: 0;
    right: 0;
    bottom: 0;
    height: 100vh !important;
  }

  @media (max-width: 640px) {
    top: -62px;
  }
}

.filter-bar__menu-search {
  max-height: 50vh;

  @media (max-width: 1024px) {
    top: 100%;
  }
}

.filter-bar__menu--save {
  right: 0;
  left: auto;
  width: 400px !important; // m-card...

  @media (max-width: 1024px) {
    left: 0;
    width: auto !important;
  }

  > div,
  > div > header {
    border-radius: 0 !important; // m-card...
  }
}

.filter-bar_menu-content {
  height: 100%;
}

.filter-bar-transition-leave-active {
  animation: slide 200ms reverse linear forwards;
  backface-visibility: hidden;
  transform-origin: top;
  z-index: -1 !important;
}

.filter-bar-transition-enter-active {
  animation: slide 200ms linear forwards;
  backface-visibility: hidden;
  transform-origin: top;
  z-index: -1 !important;
}

@keyframes slide {
  0% {
    transform: rotateX(-180deg);
  }

  100% {
    transform: rotateX(0);
  }
}

@media (max-width: 1024px) {
  @keyframes slide {
    from {
      transform: translate(0, 200%);
    }

    to {
      transform: translate(0);
    }
  }
}
</style>
