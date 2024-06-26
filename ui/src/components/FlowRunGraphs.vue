<template>
  <div class="flow-run-graphs" :class="classes.root">
    <div class="flow-run-graphs__graph-panel-container">
      <div class="flow-run-graphs__graphs">
        <FlowRunGraph
          v-model:fullscreen="fullscreen"
          v-model:viewport="dateRange"
          v-model:selected="selection"
          :flow-run
          :fetch-events
          class="flow-run-graphs__flow-run"
        />
      </div>
      <div class="flow-run-graphs__panel p-background">
        <FlowRunGraphSelectionPanel
          v-if="selection?.kind === 'task-run' || selection?.kind === 'flow-run'"
          v-model:selection="selection"
          :floating="fullscreen"
        />
      </div>
    </div>
    <FlowRunGraphEventPopover
      v-if="selection && selection.kind === 'event'"
      v-model:selection="selection"
    />
    <FlowRunGraphEventsPopover
      v-if="selection && selection.kind === 'events'"
      v-model:selection="selection"
    />
    <FlowRunGraphArtifactsPopover
      v-if="selection && selection.kind === 'artifacts'"
      v-model:selection="selection"
    />
    <FlowRunGraphStatePopover
      v-if="selection?.kind === 'state'"
      v-model:selection="selection"
    />
    <FlowRunGraphArtifactDrawer v-model:selection="selection" />
  </div>
</template>

<script lang="ts" setup>
  import {
    FlowRunGraph,
    RunGraphItemSelection,
    RunGraphViewportDateRange,
    FlowRun,
    FlowRunGraphSelectionPanel,
    FlowRunGraphArtifactDrawer,
    FlowRunGraphArtifactsPopover,
    FlowRunGraphStatePopover,
    RunGraphFetchEventsContext,
    FlowRunGraphEventPopover,
    FlowRunGraphEventsPopover,
    RunGraphEvent,
    WorkspaceEventsFilter,
    useWorkspaceApi
  } from '@prefecthq/prefect-ui-library'
  import { computed, ref } from 'vue'

  defineProps<{
    flowRun: FlowRun,
  }>()

  const api = useWorkspaceApi()
  const dateRange = ref<RunGraphViewportDateRange>()

  const fullscreen = ref(false)
  const selection = ref<RunGraphItemSelection | null>(null)

  const classes = computed(() => {
    return {
      root: {
        'flow-run-graphs--fullscreen': fullscreen.value,
        'flow-run-graphs--show-panel': Boolean(
          selection.value?.kind === 'task-run'
            || selection.value?.kind === 'flow-run',
        ),
      },
    }
  })

  const fetchEvents = async ({ nodeId, since, until }: RunGraphFetchEventsContext): Promise<RunGraphEvent[]> => {
    const filter: WorkspaceEventsFilter = {
      anyResource: {
        id: [`prefect.flow-run.${nodeId}`],
      },
      event: {
        excludePrefix: ['prefect.log.write', 'prefect.task-run.'],
      },
      occurred: {
        since,
        until,
      },
    }

    const { events } = await api.events.getEvents(filter)

    return events
  }
</script>

<style>
.flow-run-graphs { @apply
  relative;
  --flow-run-graphs-panel-width: 320px;
}

.flow-run-graphs__graph-panel-container { @apply
  relative
  grid
  grid-cols-1
  gap-2
  overflow-hidden
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
