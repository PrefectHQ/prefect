<template>
  <m-card class="filter-menu font--primary" height="100%" tabindex="0">
    <template v-if="!media.md" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <a
          v-if="media.xs"
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

        <m-icon-button
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

    <div class="filter-menu__content pa-2">
      <component
        :is="!media.md ? FilterAccordion : 'Card'"
        class="shadow-sm mb-1"
        title="Tags"
        icon="pi-filter-3-line"
      >
        <div v-if="media.md" class="filter-menu__section-header">
          <i class="filter-menu__section-header-icon pi-filter-3-line" />Tags
        </div>

        <div class="py-1 px-2" :class="{ 'd-flex': media.md }">
          <FormTags
            v-model="filters.flows.tags"
            title="Flows"
            icon="pi-flow"
            class="mb-2"
          />
          <FormTags
            v-model="filters.deployments.tags"
            title="Deployments"
            icon="pi-map-pin-line"
            class="mb-2"
          />
          <FormTags
            v-model="filters.flow_runs.tags"
            title="Flow runs"
            icon="pi-flow-run"
            class="mb-2"
          />
          <FormTags
            v-model="filters.task_runs.tags"
            title="Task runs"
            icon="pi-task"
            class="mb-2"
          />
        </div>
      </component>

      <component
        :is="!media.md ? 'template' : 'div'"
        class="d-flex align-stretch"
        :class="{ 'flex-column': !media.lg }"
      >
        <component
          :is="!media.md ? FilterAccordion : 'Card'"
          class="shadow-sm"
          :class="{
            'filter-menu__flex-card': media.md,
            'mb-1': !media.lg,
            'mr-1': media.lg
          }"
          title="States"
          icon="pi-filter-3-line"
          width="100%"
        >
          <div v-if="media.md" class="filter-menu__section-header">
            <i class="filter-menu__section-header-icon pi-filter-3-line" />
            States
          </div>

          <div class="d-flex py-1 px-2">
            <FormStates
              v-model="filters.flow_runs.states"
              title="Flow runs"
              icon="pi-flow-run"
            />
            <FormStates
              v-model="filters.task_runs.states"
              title="Task runs"
              icon="pi-task"
            />
          </div>
        </component>

        <component
          :is="!media.md ? FilterAccordion : 'Card'"
          class="shadow-sm"
          :class="{
            'filter-menu__flex-card': media.md,
            'mb-1': !media.lg && media.md
          }"
          title="Timeframes"
          icon="pi-filter-3-line"
          width="100%"
        >
          <div v-if="media.md" class="filter-menu__section-header">
            <i
              class="filter-menu__section-header-icon pi-filter-3-line"
            />Timeframes
          </div>

          <div class="d-flex py-1 px-2" :class="!media.md ? 'flex-column' : ''">
            <FormDateTime
              v-model="filters.flow_runs.timeframe"
              class="mr-1"
              title="Flow runs"
              icon="pi-flow-run"
            />
            <FormDateTime
              v-model="filters.task_runs.timeframe"
              title="Task runs"
              icon="pi-task"
            />
          </div>
        </component>
      </component>
    </div>

    <template v-slot:actions>
      <CardActions
        class="pa-2 filter-menu__actions d-flex align-center justify-end"
      >
        <m-button
          v-if="media.md"
          flat
          height="35px"
          class="ml-auto mr-1"
          @click="close"
        >
          Cancel
        </m-button>
        <m-button
          color="primary"
          height="35px"
          :width="!media.md ? '100%' : 'auto'"
          @click="apply"
        >
          Apply
        </m-button>
      </CardActions>
    </template>
  </m-card>
</template>

<script lang="ts" setup>
import { ref, readonly } from 'vue'
import { useStore } from '@/store'
import FilterAccordion from './FilterAccordion.vue'
import FormTags from './composables/Form--Tags.vue'
import FormStates from './composables/Form--States.vue'
import FormDateTime from './composables/Form--DateTime.vue'
import { media } from '@prefecthq/orion-design/utilities'
import { GlobalFilter, RunTimeFrame } from '@/typings/global'
import { GlobalFilterDefaults } from '@prefecthq/orion-design/models'

const emit = defineEmits(['close'])
const store = useStore()

const current = readonly(store.state.filter)
const defaults: GlobalFilter = new GlobalFilterDefaults()

const defaultTimeFrame: RunTimeFrame = {
  dynamic: false,
  from: { unit: 'minutes', value: undefined, timestamp: undefined },
  to: { unit: 'minutes', value: undefined, timestamp: undefined }
}

const filters = ref<GlobalFilter>({
  flows: {
    ids: [...(current.flows.ids ?? defaults.flows.ids ?? [])],
    names: [...(current.flows.names ?? defaults.flows.names ?? [])],
    tags: [...(current.flows.tags ?? defaults.flows.tags ?? [])]
  },
  deployments: {
    ids: [...(current.deployments.ids ?? defaults.deployments.ids ?? [])],
    names: [...(current.deployments.names ?? defaults.deployments.names ?? [])],
    tags: [...(current.deployments.tags ?? defaults.deployments.tags ?? [])]
  },
  flow_runs: {
    ids: [...(current.flow_runs.ids ?? defaults.flow_runs.ids ?? [])],
    tags: [...(current.flow_runs.tags ?? defaults.flow_runs.tags ?? [])],
    states: [...(current.flow_runs.states ?? defaults.flow_runs.states ?? [])],
    timeframe: {
      ...(current.flow_runs.timeframe ?? defaults.flow_runs.timeframe ?? defaultTimeFrame)
    }
  },
  task_runs: {
    ids: [...(current.task_runs.ids ?? defaults.task_runs.ids ?? [])],
    tags: [...(current.task_runs.tags ?? defaults.task_runs.tags ?? [])],
    states: [...(current.task_runs.states ?? defaults.task_runs.states ?? [])],
    timeframe: {
      ...(current.task_runs.timeframe ?? defaults.task_runs.timeframe ?? defaultTimeFrame)
    }
  }
})

const apply = () => {
  store.commit('filter/setFilter', { ...filters.value })
  emit('close')
}

const close = () => {
  emit('close')
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-menu.scss';
</style>
