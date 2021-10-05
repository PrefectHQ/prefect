<template>
  <Card class="menu font--primary" height="100%" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-space-between align-center">
        <a
          class="
            text--primary text-decoration-none
            font--secondary
            caption
            nowrap
          "
        >
          Clear all
        </a>

        <h3 class="d-flex align-center font--secondary">
          <i class="pi pi-filter-3-line mr-1" />
          Filters
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          flat
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content pa-2">
      <!-- <div class="d-flex align-center flex-grow-1 justify-start"> -->
      <FilterAccordion class="mb-1" title="Flows" icon="pi-filter-3-line">
        <div class="accordion-body">
          <TagsForm v-model="filters.flows.tags" class="px-2 py-1" />
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Deployments" icon="pi-filter-3-line">
        <div class="accordion-body">
          <TagsForm v-model="filters.deployments.tags" />
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Flow Runs" icon="pi-filter-3-line">
        <div class="accordion-body">
          <StatesForm v-model="filters.flow_runs.states" class="px-2 py-1" />
          <TagsForm v-model="filters.flow_runs.tags" class="px-2 py-1" />
          <!-- <TimeForm v-model="filters.flow_runs.timeframe" class="px-2 py-1" /> -->
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Task Runs" icon="pi-filter-3-line">
        <div class="accordion-body">
          <StatesForm v-model="filters.task_runs.states" class="px-2 py-1" />
          <TagsForm v-model="filters.task_runs.tags" />
          <!-- <TimeForm v-model="filters.task_runs.timeframe" class="px-2 py-1" /> -->
        </div>
      </FilterAccordion>
      <!-- <Button
          v-for="(menu, i) in menuButtons"
          :key="i"
          class="mr-2"
          height="36px"
          :ref="(el) => elRef(el, i)"
          @click="toggleMenu(i)"
        >
          <i class="pi" :class="menu.icon ? menu.icon : 'pi-filter-3-line'" />
          <span class="text-capitalize ml-1">{{ menu.label }}</span>
        </Button>
      </div>

      <div v-if="filters.length" class="mt-2 d-flex align-center justify-start">
        <FilterTag
          v-for="(filter, i) in filters"
          :key="i"
          :item="filter"
          class="mr--half"
          @click.self="handleTagClick(filter)"
          @remove="removeFilter"
        /> -->
      <!-- </div> -->
    </div>

    <template v-slot:actions>
      <CardActions class="pa-2 menu-actions d-flex align-center justify-end">
        <Button
          v-if="!smAndDown"
          flat
          height="35px"
          class="ml-auto mr-1"
          @click="close"
        >
          Cancel
        </Button>
        <Button
          color="primary"
          height="35px"
          :width="smAndDown ? '100%' : 'auto'"
        >
          Apply
        </Button>
      </CardActions>
    </template>

    <!-- <component
      v-for="(menu, i) in menus.filter((m) => m.show)"
      :key="i"
      :is="menu.component"
      v-model="selectedObject"
      class="sub-menu"
      :object="selectedObject"
      :style="subMenuStyle"
      @close="menu.show = false"
    /> -->
  </Card>
</template>

<script lang="ts" setup>
import {
  ref,
  reactive,
  shallowRef,
  computed,
  ComponentPublicInstance,
  defineEmits,
  watch
} from 'vue'
import { useStore } from 'vuex'
// import TimeForm from './Form--DateTime.vue'
// import ObjectMenu from './ObjectMenu.vue'
// import FilterTag from './FilterTag.vue'
import { parseFilters, FilterObject } from './util'
import { getCurrentInstance } from 'vue'
import FilterAccordion from './FilterAccordion.vue'

import TagsForm from './Form--Tags.vue'
import StatesForm from './Form--States.vue'
import TimeForm from './Form--DateTime.vue'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])
const store = useStore()

const iconMap: { [key: string]: string } = {
  flow_runs: 'pi-flow-run',
  task_runs: 'pi-task',
  flows: 'pi-flow',
  deployments: 'pi-map-pin-line'
}

console.log(store.getters.globalFilter)

const gf = store.getters.globalFilter
const defaultFilters = {
  flows: {
    tags: gf.flows.tags || []
  },
  deployments: { tags: gf.deployments.tags || [] },
  flow_runs: {
    tags: gf.flow_runs.tags || [],
    states: gf.flow_runs.states || []
  },
  task_runs: {
    tags: gf.task_runs.tags || [],
    states: gf.task_runs.states || []
  }
}

console.log(defaultFilters)

const filters = reactive(defaultFilters)

watch(filters, () => {
  console.log(filters)
})

// TODO: This is really hacky so we probably want to refactor sooner rather than later.
// const menus = reactive([
//   {
//     key: 'object',
//     label: computed(() => selectedObject.value.replace('_', ' ')),
//     component: shallowRef(ObjectMenu),
//     icon: computed(() => iconMap[selectedObject.value]),
//     show: false,
//     objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
//   },
//   {
//     key: 'states',
//     label: 'Run States',
//     component: shallowRef(RunStatesMenu),
//     show: false,
//     objects: ['flow_runs', 'task_runs']
//   },
//   {
//     key: 'timeframe',
//     label: 'Timeframe',
//     component: shallowRef(TimeframeMenu),
//     show: false,
//     objects: ['flow_runs', 'task_runs']
//   },
//   {
//     key: 'tags',
//     label: 'Tags',
//     component: shallowRef(TagsMenu),
//     show: false,
//     objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
//   }
// ])

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})

const close = () => {
  emit('close')
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-menu.scss';
</style>
