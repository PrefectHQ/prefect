<template>
  <Card class="menu font--primary" height="100%" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <a
          v-breakpoints="'xs'"
          class="
            text--primary text-decoration-none
            font--secondary
            caption
            nowrap
          "
        >
          Clear all
        </a>

        <h3 class="d-flex align-center font--secondary ml-auto">
          <i class="pi pi-filter-3-line mr-1" />
          Filters
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          class="ml-auto"
          flat
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content pa-2">
      <FilterAccordion class="mb-1" title="Flows" icon="pi-filter-3-line">
        <div class="accordion-body">
          <TagsForm v-model="filters.flows.tags" class="px-2 py-1" />
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Deployments" icon="pi-filter-3-line">
        <div class="accordion-body">
          <TagsForm v-model="filters.deployments.tags" class="px-2 py-1" />
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Flow Runs" icon="pi-filter-3-line">
        <div class="accordion-body">
          <StatesForm v-model="filters.flow_runs.states" class="px-2 py-1" />
          <TimeForm v-model="filters.flow_runs.timeframe" class="px-2 py-1" />
          <TagsForm v-model="filters.flow_runs.tags" class="px-2 py-1" />
        </div>
      </FilterAccordion>
      <FilterAccordion class="mb-1" title="Task Runs" icon="pi-filter-3-line">
        <div class="accordion-body">
          <StatesForm v-model="filters.task_runs.states" class="px-2 py-1" />
          <TagsForm v-model="filters.task_runs.tags" class="px-2 py-1" />
          <!-- <TimeForm v-model="filters.task_runs.timeframe" class="px-2 py-1" /> -->
        </div>
      </FilterAccordion>
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
          @click="apply"
        >
          Apply
        </Button>
      </CardActions>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { ref, computed, defineEmits, getCurrentInstance, readonly } from 'vue'
import { useStore } from 'vuex'

import FilterAccordion from './FilterAccordion.vue'
import TagsForm from './Form--Tags.vue'
import StatesForm from './Form--States.vue'
import TimeForm from './Form--DateTime.vue'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])
const store = useStore()

const gf = readonly(store.getters.globalFilter)

const defaultFilters = {
  flows: {
    ids: [...(gf.flows.ids || [])],
    names: [...(gf.flows.names || [])],
    tags: [...(gf.flows.tags || [])]
  },
  deployments: {
    ids: [...(gf.deployments.ids || [])],
    names: [...(gf.deployments.names || [])],
    tags: [...(gf.deployments.tags || [])]
  },
  flow_runs: {
    ids: [...(gf.flow_runs.ids || [])],
    tags: [...(gf.flow_runs.tags || [])],
    states: [...(gf.flow_runs.states || [])],
    timeframe: {
      ...(gf.flow_runs.timeframe || {
        dynamic: false,
        from: { units: 'minutes', value: 60, timestamp: null },
        to: { units: 'minutes', value: 60, timestamp: null }
      })
    }
  },
  task_runs: {
    ids: [...(gf.task_runs.ids || [])],
    tags: [...(gf.task_runs.tags || [])],
    states: [...(gf.task_runs.states || [])],
    timeframe: {
      ...(gf.task_runs.timeframe || {
        dynamic: false,
        from: { units: 'minutes', value: 60, timestamp: null },
        to: { units: 'minutes', value: 60, timestamp: null }
      })
    }
  }
}

const filters = ref({ ...defaultFilters })

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})

const apply = () => {
  store.commit('globalFilter', { ...filters.value })
  emit('close')
}

const close = () => {
  emit('close')
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-menu.scss';
</style>
