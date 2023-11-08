<template>
  <div class="flow-run-graphs" :class="classes.root">
    <div class="flow-run-graphs__graphs">
      <FlowRunGraph
        v-model:fullscreen="fullscreen"
        v-model:viewport="dateRange"
        v-model:selected="selectedNode"
        :flow-run="flowRun"
        class="flow-run-graphs__flow-run"
      />
    </div>
    <div class="flow-run-graphs__panel p-background">
      <FlowRunGraphSelectionPanel
        v-model:node="selectedNode"
        :floating="fullscreen"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import {
    FlowRunGraph,
    RunGraphNodeSelection,
    RunGraphViewportDateRange,
    FlowRun,
    FlowRunGraphSelectionPanel
  } from '@prefecthq/prefect-ui-library'
  import { computed, ref } from 'vue'

  defineProps<{
    flowRun: FlowRun,
  }>()

  const dateRange = ref<RunGraphViewportDateRange>()

  const fullscreen = ref(false)
  const selectedNode = ref<RunGraphNodeSelection | null>(null)

  const classes = computed(() => {
    return {
      root: {
        'flow-run-graphs--fullscreen': fullscreen.value,
        'flow-run-graphs--show-panel': Boolean(selectedNode.value),
      },
    }
  })
</script>

<style>
.flow-run-graphs { @apply
  relative
  grid
  grid-cols-1
  gap-2
  overflow-hidden;
  --flow-run-graphs-panel-width: 320px;
}

.flow-run-graphs--fullscreen { @apply
  z-20
  static
}

.flow-run-graphs__graphs { @apply
  transition-[width];
  width: 100%;
}

.flow-run-graphs--show-panel .flow-run-graphs__graphs {
  width: calc(100% - var(--flow-run-graphs-panel-width) - theme(spacing.2));
}

.flow-run-graphs__flow-run { @apply
  overflow-hidden
  rounded
}

.flow-run-graphs__panel { @apply
  absolute
  right-0
  top-0
  bottom-0
  translate-x-full
  transition-transform
  rounded;
  width: var(--flow-run-graphs-panel-width)
}

.flow-run-graphs--fullscreen .flow-run-graphs__panel { @apply
  bg-floating
  top-4
  right-4
  bottom-auto
}

.flow-run-graphs--show-panel .flow-run-graphs__panel { @apply
  translate-x-0
}
</style>
