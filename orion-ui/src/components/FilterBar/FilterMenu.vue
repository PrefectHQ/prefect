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

        <h3
          class="d-flex align-center font--primary font-weight-semibold ml-auto"
        >
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

    <div v-if="smAndDown" class="menu-content pa-2">
      <FilterAccordion class="mb-1" title="Tags" icon="pi-filter-3-line">
        <div class="py-1 px-2">
          <Form-Tags
            v-model="filters.flows.tags"
            title="Flows"
            icon="pi-flow"
            class="mb-2"
          />
          <Form-Tags
            v-model="filters.deployments.tags"
            title="Deployments"
            icon="pi-map-pin-line"
            class="mb-2"
          />
          <Form-Tags
            v-model="filters.flow_runs.tags"
            title="Flow runs"
            icon="pi-flow-run"
            class="mb-2"
          />
          <Form-Tags
            v-model="filters.task_runs.tags"
            title="Task runs"
            icon="pi-task"
            class="mb-2"
          />
        </div>
      </FilterAccordion>

      <FilterAccordion class="mb-1" title="States" icon="pi-filter-3-line">
        <div class="d-flex py-1 px-2">
          <Form-States
            v-model="filters.flow_runs.states"
            title="Flow runs"
            icon="pi-flow-run"
          />
          <Form-States
            v-model="filters.task_runs.states"
            title="Task runs"
            icon="pi-task"
          />
        </div>
      </FilterAccordion>

      <FilterAccordion title="Timeframes" icon="pi-filter-3-line">
        <div class="d-flex py-1 px-2" :class="smAndDown ? 'flex-column' : ''">
          <Form-DateTime
            v-model="filters.flow_runs.timeframe"
            class="mr-1"
            title="Flow runs"
            icon="pi-flow-run"
          />
          <Form-DateTime
            v-model="filters.task_runs.timeframe"
            title="Task runs"
            icon="pi-task"
          />
        </div>
      </FilterAccordion>
    </div>

    <div v-else class="menu-content pa-2">
      <Card class="shadow-sm mb-1">
        <div
          class="py-1 px-2 d-flex align-center font-weight-semibold text--black"
        >
          <i class="pi pi-filter-3-line mr-1 pi-sm" />Tags
        </div>
        <div class="d-flex py-1 px-2">
          <Form-Tags
            v-model="filters.flows.tags"
            title="Flows"
            icon="pi-flow"
            class="mr-1"
          />
          <Form-Tags
            v-model="filters.deployments.tags"
            title="Deployments"
            icon="pi-map-pin-line"
            class="mr-1"
          />
          <Form-Tags
            v-model="filters.flow_runs.tags"
            title="Flow runs"
            icon="pi-flow-run"
            class="mr-1"
          />
          <Form-Tags
            v-model="filters.task_runs.tags"
            title="Task runs"
            icon="pi-task"
          />
        </div>
      </Card>

      <div class="d-flex align-stretch" :class="{ 'flex-column': mdAndDown }">
        <Card
          class="shadow-sm flex-card"
          width="100%"
          :class="mdAndDown ? 'mb-1' : 'mr-1'"
        >
          <div
            class="
              py-1
              px-2
              d-flex
              align-center
              font-weight-semibold
              text--black
            "
          >
            <i class="pi pi-filter-3-line mr-1 pi-sm" />States
          </div>

          <div class="d-flex py-1 px-2">
            <Form-States
              v-model="filters.flow_runs.states"
              title="Flow runs"
              icon="pi-flow-run"
            />
            <Form-States
              v-model="filters.task_runs.states"
              title="Task runs"
              icon="pi-task"
            />
          </div>
        </Card>

        <Card
          class="shadow-sm flex-card"
          width="100%"
          :class="{ 'mb-1': mdAndDown }"
        >
          <div
            class="
              py-1
              px-2
              d-flex
              align-center
              font-weight-semibold
              text--black
            "
          >
            <i class="pi pi-filter-3-line mr-1 pi-sm" />Timeframes
          </div>

          <div class="d-flex py-1 px-2 align-stretch">
            <Form-DateTime
              v-model="filters.flow_runs.timeframe"
              title="Flow runs"
              icon="pi-flow-run"
              class="mr-4 mb-1"
            />
            <Form-DateTime
              v-model="filters.task_runs.timeframe"
              title="Task runs"
              icon="pi-task"
            />
          </div>
        </Card>
      </div>
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

import FormTags from './composables/Form--Tags.vue'
import FormStates from './composables/Form--States.vue'
import FormDateTime from './composables/Form--DateTime.vue'

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

const mdAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.lg
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
