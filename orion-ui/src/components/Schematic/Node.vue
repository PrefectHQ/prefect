<template>
  <div
    ref="observe"
    class="node d-flex position-relative"
    :class="{
      observed: observed,
      [state.type.toLowerCase() + '-border']: true
    }"
  >
    <div
      class="d-flex align-center justify-center border px-1"
      :class="state.type.toLowerCase() + '-bg'"
    >
      <i
        class="pi text--white pi-lg"
        :class="'pi-' + state.type.toLowerCase()"
      />
    </div>

    <div
      class="d-flex align-stretch flex-column justify-center px-1 flex-grow-1"
      style="min-width: 0"
    >
      <div
        v-skeleton="!taskRun.name"
        v-tooltip.top="taskRun.name"
        class="text-truncate"
      >
        {{ taskRun.name }}
      </div>

      <div class="d-flex align-center justify-space-between">
        <div
          v-skeleton="!taskRun.estimated_run_time"
          class="
            text-truncate
            font--secondary
            caption
            flex-grow-1 flex-shrink-0
          "
        >
          {{ duration }}
        </div>

        <a
          v-if="node.downstreamNodes.size > 0"
          class="collapse-link caption-small flex-shrink"
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
import { Api, Endpoints, Query } from '@/plugins/api'
import { SchematicNode } from '@/typings/schematic'
import { State, TaskRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'

const emit = defineEmits(['toggle-tree'])

const props = defineProps<{
  node: SchematicNode
  collapsed?: undefined | Map<string, SchematicNode>
}>()

const queries: { [key: string]: Query } = {
  task_run: Api.query({
    endpoint: Endpoints.task_run,
    body: {
      id: props.node.id
    },
    options: {
      pollInterval: 5000,
      paused: true
    }
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
  return props.node.data.state
})

const duration = computed<string>(() => {
  return taskRun.value
    ? secondsToApproximateString(taskRun.value.estimated_run_time)
    : '--'
})

const taskRun = computed<TaskRun>(() => {
  return queries.task_run.response.value || {}
})

/**
 * Intersection Observer
 */

const observed: Ref<boolean> = ref(false)

const handleEmit = ([entry]: IntersectionObserverEntry[]) => {
  if (entry.isIntersecting) {
    observed.value = entry.isIntersecting
    queries.task_run.resume()
  } else {
    queries.task_run.pause()
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

watch(taskRun, () => {
  if (terminalStates.includes(taskRun.value?.state_type)) {
    queries.task_run.pollInterval = 0
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
  background-color: white;
  border-radius: 10px;
  box-shadow: 0px 0px 6px rgb(8, 29, 65, 0.06);
  box-sizing: content-box;
  // These don't work in firefox yet but are being prototyped (https://github.com/mozilla/standards-positions/issues/135)
  contain-intrinsic-size: 53px;
  content-visibility: auto;
  cursor: pointer;
  position: absolute;
  height: 53px;
  pointer-events: all;
  transition: top 150ms, left 150ms, transform 150ms, box-shadow 50ms;
  transform: translate(-50%, -50%);
  width: 275px;

  &.observed {
    visibility: visible;
  }

  &:hover {
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
  }

  &:focus {
    border-width: 2px;
    border-style: solid;
    transition: border-color 150ms;
    outline: none;
  }

  .border {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    height: 100%;
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

.scale-enter-active,
.scale-leave-active {
  transition: transform 150ms ease;
}

.scale-enter-from,
.scale-leave-to {
  transform: scale(0);
}
</style>
