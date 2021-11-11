<template>
  <div
    v-if="true"
    ref="observe"
    class="node d-flex position-relative"
    :class="{
      observed: observed,
      [state.type.toLowerCase() + '-border']: true,
      [state.type.toLowerCase() + '-bg']: true,
      selected: props.selected
    }"
    @click="handleClick"
  >
    <div
      class="d-flex align-self-stretch align-center justify-center border px-1"
    >
      <i
        class="pi text--white pi-lg"
        :class="'pi-' + state.type.toLowerCase()"
      />
    </div>

    <div
      class="
        d-flex
        align-stretch
        flex-column
        justify-start
        px-1
        flex-grow-1
        content
      "
      style="min-width: 0"
    >
      <div
        v-skeleton="!flowRun.name"
        class="text-truncate d-flex align-center justify-space-between"
      >
        {{ flowRun.name }} <i class="pi pi-flow-run pi-xs" />
      </div>

      <div class="d-flex align-center justify-start">
        <div
          v-skeleton="!flowRun.name"
          class="
            text-truncate
            font--secondary
            caption
            flex-grow-1 flex-shrink-0
          "
        >
          {{ duration }}
          <!-- {{ flowRun && flowRun.id && flowRun.id.slice(0, 8) }} -->
        </div>
        <router-link :to="`/flow-run/${flowRunId}/schematic`">
          <ButtonRounded>
            {{ taskRunCount }} task run{{ taskRunCount == 1 ? '' : 's' }}
          </ButtonRounded>
        </router-link>
      </div>

      <div class="d-flex align-center justify-space-between mt-auto mb-1">
        <a
          v-if="node.downstreamNodes.size > 0"
          class="collapse-link caption-small flex-shrink ml-auto"
          tabindex="-1"
          @click.stop="toggle"
        >
          {{ collapsed ? 'Show' : 'Hide' }}
        </a>
      </div>
    </div>

    <transition name="scale" mode="out-in">
      <div v-if="collapsed" class="position-absolute collapsed-badge caption">
        {{ collapsed.size.toLocaleString() }}
      </div>
    </transition>
  </div>
  <div
    v-else
    class="circle-node cursor-pointer"
    :class="state.type.toLowerCase() + '-bg'"
  />
</template>

<script lang="ts" setup>
import {
  defineProps,
  computed,
  defineEmits,
  onMounted,
  onBeforeUnmount,
  Ref,
  ref,
  watch
} from 'vue'
import { Api, Endpoints, Query, TaskRunsFilter } from '@/plugins/api'
import { SchematicNode } from '@/typings/schematic'
import { State, FlowRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'

const emit = defineEmits(['toggle-tree'])

const props = defineProps<{
  node: SchematicNode
  collapsed?: undefined | Map<string, SchematicNode>
  selected?: boolean
}>()

const flowRunId = computed<string>(() => {
  return props.node.data.state.state_details.child_flow_run_id
})

const flow_runs_filter_body: TaskRunsFilter = {
  sort: 'START_TIME_DESC',
  flow_runs: {
    id: {
      any_: [flowRunId.value]
    }
  },
  task_runs: {
    subflow_runs: {
      exists_: false
    }
  }
}

const queries: { [key: string]: Query } = {
  flow_run: Api.query({
    endpoint: Endpoints.flow_run,
    body: {
      id: flowRunId.value
    },
    options: {
      pollInterval: 5000
    }
  }),
  task_run_count: Api.query({
    endpoint: Endpoints.task_runs_count,
    body: flow_runs_filter_body
  })
}

const toggle = () => {
  emit('toggle-tree', props.node)
}

const node = computed<SchematicNode>(() => {
  return props.node
})

const collapsed = computed(() => {
  return props.collapsed
})

const state = computed<State>(() => {
  return flowRun.value?.state || props.node.data.state
})

const duration = computed<string>(() => {
  return flowRun.value?.estimated_run_time
    ? secondsToApproximateString(flowRun.value.estimated_run_time)
    : '--'
})

const flowRun = computed<FlowRun>(() => {
  return queries.flow_run.response.value || {}
})

const taskRunCount = computed((): number => {
  return queries.task_run_count?.response?.value || 0
})

const handleClick = () => {
  console.log(flowRun.value)
}

/**
 * Intersection Observer
 */

const observed: Ref<boolean> = ref(false)

const handleEmit = ([entry]: IntersectionObserverEntry[]) => {
  if (entry.isIntersecting) {
    observed.value = entry.isIntersecting
    queries.flow_run.resume()
  } else {
    queries.flow_run.pause()
  }
}

const observe = ref<Element>()

let observer: IntersectionObserver

const createIntersectionObserver = (margin: string) => {
  if (observe.value) observer?.unobserve(observe.value)

  const options = {
    rootMargin: margin,
    threshold: [0.5, 1]
  }

  observer = new IntersectionObserver(handleEmit, options)
  if (observe.value) observer.observe(observe.value)
}

const terminalStates = ['COMPLETED', 'FAILED', 'CANCELLED']

watch(flowRun, () => {
  if (terminalStates.includes(flowRun.value?.state_type)) {
    queries.flow_run.pollInterval = 0
  }
})

onMounted(() => {
  createIntersectionObserver('12px')
})

onBeforeUnmount(() => {
  if (observe.value) observer?.unobserve(observe.value)
})
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.node {
  visibility: hidden;
  background-color: red;
  border-radius: 10px;
  box-shadow: 0px 0px 6px rgb(8, 29, 65, 0.06);
  box-sizing: content-box;
  // These don't work in firefox yet but are being prototyped (https://github.com/mozilla/standards-positions/issues/135)
  contain-intrinsic-size: 300px 60px;
  content-visibility: hidden;
  overflow: visible;
  cursor: pointer;
  height: 125px;
  pointer-events: all;
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);
  width: 275px;

  &.observed {
    visibility: visible;
    content-visibility: visible;
  }

  &:hover {
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  }

  &.selected {
    border-width: 2px;
    border-style: solid;
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
    transition: border-color 150ms;
    outline: none;
  }

  .content {
    background-color: #fff;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
  }

  .border {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
  }

  .collapse-link {
    &:hover {
      background-color: var(--grey-5);
    }

    > i {
      color: rgba(0, 0, 0, 0.3);
    }
  }

  .collapsed-badge {
    background-color: $primary;
    border-radius: 99999999px; // Ensures a consistent border radius
    color: $white;
    padding: 2px 4px;
    right: -2%;
    top: -7.5px;
  }
}

.circle-node {
  border-radius: 50%;
  height: 34px;
  width: 34px;
  transform: translate(-50%, -50%);
  z-index: 1;
  cursor: pointer;
}

.scale-enter-active,
.scale-leave-active {
  transition: transform 150ms ease;
}

.scale-enter-from,
.scale-leave-to {
  transform: scale(0);
}
</style>
