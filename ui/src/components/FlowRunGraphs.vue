<template>
  <div class="flow-run-graphs" :class="classes.root">
    <div class="flow-run-graphs__graphs" :class="classes.graph">
      <FlowRunTimeline
        class="flow-run-graphs__timeline"
        :flow-run="flowRun"
        height="340px"
        :selected-node="selectedNode"
        @selection="selectNode"
        @update:fullscreen="(event: boolean) => isFullscreen = event"
      />
    </div>
    <div
      class="flow-run-graphs__panel-container"
      :class="classes.panel"
    >
      <div class="flow-run-graphs__panel-content">
        <FlowRunTimelineSelectionPanel
          :selected-node="selectedNode"
          :floating="isFullscreen"
          @dismiss="closePanel"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { NodeSelectionEvent } from '@prefecthq/graphs'
  import {
    FlowRunTimeline,
    FlowRun,
    FlowRunTimelineSelectionPanel
  } from '@prefecthq/prefect-ui-library'
  import { computed, ref } from 'vue'

  defineProps<{
    flowRun: FlowRun,
  }>()

  const isFullscreen = ref(false)
  const selectedNode = ref<NodeSelectionEvent | null>(null)
  const panelOpen = ref(false)

  const classes = computed(() => {
    return {
      root: {
        'flow-run-graphs--fullscreen': isFullscreen.value,
      },
      graph: {
        'flow-run-graphs__graphs--panel-open': panelOpen.value,
      },
      panel: {
        'flow-run-graphs__panel-container--panel-open': panelOpen.value,
      },
    }
  })

  function selectNode(event: NodeSelectionEvent | null): void {
    selectedNode.value = event
    panelOpen.value = !!event
  }

  function closePanel(): void {
    panelOpen.value = false
  }
</script>

<style>
.flow-run-graphs {
  --flow-run-graphs-panel-width: 320px;
  @apply
  relative
}
.flow-run-graphs--fullscreen { @apply
  static
}

.flow-run-graphs__timeline { @apply
  bg-background
  rounded-lg
  overflow-hidden
}

.flow-run-graphs__panel-container {
  @apply
  absolute
  top-0
  right-0
  bottom-0
  z-20
  w-0
  max-w-full
  opacity-0
  overflow-hidden
}
.flow-run-graphs__panel-container--panel-open {
  width: var(--flow-run-graphs-panel-width);
  transition: none;
  @apply
  opacity-100
}
.flow-run-graphs__panel-content {
  width: var(--flow-run-graphs-panel-width);
  @apply
  absolute
  h-full
  max-w-full
  translate-x-full
  transition-transform
  duration-300
}
.flow-run-graphs__panel-container--panel-open .flow-run-graphs__panel-content { @apply
  translate-x-0
}

.flow-run-graphs--fullscreen .flow-run-graphs__panel-container { @apply
  h-auto
  top-4
  right-4
  bottom-auto
}
.flow-run-graphs--fullscreen .flow-run-graphs__panel-content { @apply
  static
  h-auto
}

@screen sm {
  .flow-run-graphs__graphs--panel-open {
    width: calc(100% - var(--flow-run-graphs-panel-width));
    @apply
    pr-2
  }
  .flow-run-graphs--fullscreen .flow-run-graphs__graphs--panel-open { @apply
    w-full
    z-20
  }
}
</style>
