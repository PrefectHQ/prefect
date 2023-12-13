<template>
  <p-layout-default class="workspace-dashboard">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template v-if="!empty" #actions>
          <FlowRunTagsInput v-model:selected="filter.tags" empty-message="All tags" class="workspace-dashboard__tags" />
          <DateRangeSelect v-model="filter.range" class="workspace-dashboard__range" />
        </template>
      </PageHeading>
    </template>
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
    <MarketingBanner
      title="Ready to scale?"
      subtitle="Automations, role and object-level security, and serverless push work pools on Prefect Cloud"
    >
      <template #actions>
        <p-button to="https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss&utm_term=none&utm_content=none" target="_blank" primary>
          Upgrade to Cloud
        </p-button>
      </template>
    </MarketingBanner>
  </p-layout-default>
</template>

<script setup lang="ts">
  import { Crumb } from '@prefecthq/prefect-design'
  import {
    DashboardWorkPoolsCard,
    WorkspaceDashboardFlowRunsCard,
    CumulativeTaskRunsCard,
    PageHeading,
    FlowRunTagsInput,
    FlowRunsPageEmptyState,
    useWorkspaceApi,
    subscriptionIntervalKey,
    mapper,
    TaskRunsFilter,
    MarketingBanner,
    Getter,
    DateRangeSelect,
    useWorkspaceDashboardFilterFromRoute
  } from '@prefecthq/prefect-ui-library'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { secondsInDay, secondsToMilliseconds } from 'date-fns'
  import { computed, provide } from 'vue'

  provide(subscriptionIntervalKey, {
    interval: secondsToMilliseconds(30),
  })

  const api = useWorkspaceApi()
  const flowRunsCountAllSubscription = useSubscription(api.flowRuns.getFlowRunsCount, [{}])
  const loaded = computed(() => flowRunsCountAllSubscription.executed)
  const empty = computed(() => flowRunsCountAllSubscription.response === 0)
  const crumbs: Crumb[] = [{ text: 'Dashboard' }]

  const filter = useWorkspaceDashboardFilterFromRoute({
    range: { type: 'span', seconds: -secondsInDay },
    tags: [],
  })

  const tasksFilter: Getter<TaskRunsFilter> = () => mapper.map('WorkspaceDashboardFilter', filter, 'TaskRunsFilter')
</script>

<style>
.workspace-dashboard__tags { @apply
  w-full
  max-w-xs
}

.workspace-dashboard__range { @apply
  max-w-lg
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