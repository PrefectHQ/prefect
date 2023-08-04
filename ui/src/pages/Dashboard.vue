<template>
  <p-layout-default class="workspace-dashboard">
    <PageHeading :crumbs="crumbs">
      <template v-if="!empty" #actions>
        <FlowRunTagsInput v-model:selected="tags" :filter="{}" empty-message="All tags" class="workspace-dashboard__tags" />
        <TimeSpanFilter v-model:selected="timeSpanInSeconds" />
      </template>
    </PageHeading>
    <template v-if="loaded">
      <template v-if="empty">
        <FlowRunsPageEmptyState />
      </template>
      <template v-else>
        <div class="workspace-dashboard__grid">
          <WorkspaceDashboardFlowRunsCard :filter="filter" />
          <div class="workspace-dashboard__side">
            <CumulativeTaskRunsCard :filter="tasksFilter" />
            <DashboardWorkPoolsCard class="workspace-dashboard__work-pools" :filter="filter" />
          </div>
        </div>
      </template>
    </template>
  </p-layout-default>
</template>

<script setup lang="ts">
  import { Crumb } from '@prefecthq/prefect-design'
  import {
    TimeSpanFilter,
    DashboardWorkPoolsCard,
    WorkspaceDashboardFilter,
    WorkspaceDashboardFlowRunsCard,
    CumulativeTaskRunsCard,
    PageHeading,
    FlowRunTagsInput,
    FlowRunsPageEmptyState,
    useWorkspaceApi,
    subscriptionIntervalKey,
    mapper,
    TaskRunsFilter,
    Getter
  } from '@prefecthq/prefect-ui-library'
  import { NumberRouteParam, useRouteQueryParam, useSubscription } from '@prefecthq/vue-compositions'
  import { secondsInHour, secondsToMilliseconds } from 'date-fns'
  import { computed, provide } from 'vue'

  provide(subscriptionIntervalKey, {
    interval: secondsToMilliseconds(30),
  })

  const api = useWorkspaceApi()
  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)

  const crumbs: Crumb[] = [{ text: 'Dashboard' }]

  const timeSpanInSeconds = useRouteQueryParam('span', NumberRouteParam, secondsInHour * 24)
  const tags = useRouteQueryParam('tags', [])

  const filter = computed<WorkspaceDashboardFilter>(() => ({
    timeSpanInSeconds: timeSpanInSeconds.value,
    tags: tags.value,
  }))

  const tasksFilter: Getter<TaskRunsFilter> = () => mapper.map('WorkspaceDashboardFilter', filter.value, 'TaskRunsFilter')
</script>

<style>
.workspace-dashboard__tags { @apply
  w-full
  max-w-xs
}

.workspace-dashboard__grid { @apply
  grid
  grid-cols-1
  gap-4
  items-start
}

@screen xl {
  .workspace-dashboard__grid { @apply
    grid-cols-2
  }
}

.workspace-dashboard__side { @apply
  grid
  grid-cols-1
  gap-4
}
</style>