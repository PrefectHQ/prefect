<template>
  <ListItem class="flows-page-flow-list-item">
    <div class="flows-page-flow-list-item__name">
      <BreadCrumbs :crumbs="crumbs" tag="h2" @click="openFlowPanel" />
    </div>

    <div class="flows-page-flow-list-item__details">
      <m-tag icon="pi-map-pin-line" flat>
        {{ deploymentsCount.toLocaleString() }}
        {{ toPluralString('Deployment', deploymentsCount) }}
      </m-tag>
      <m-tags class="flows-page-flow-list-item__tags" :tags="flow.tags" />
    </div>

    <FilterCountButton class="flows-page-flow-list-item__recent" :count="recentFlowRunsCount" label="Recent Run" :route="route" :filters="recentFlowRunsFilters" />
  </ListItem>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { subWeeks, startOfToday } from 'date-fns'
  import { computed, inject } from 'vue'
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import DeploymentPanel from '@/components/DeploymentPanel.vue'
  import FilterCountButton from '@/components/FilterCountButton.vue'
  import FlowPanel from '@/components/FlowPanel.vue'
  import ListItem from '@/components/ListItem.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { Deployment } from '@/models/Deployment'
  import { Flow } from '@/models/Flow'
  import { workspaceDashboardKey } from '@/router/routes'
  import { UnionFilters } from '@/services/Filter'
  import { Filter } from '@/types/filters'
  import { showPanel } from '@/utilities/panels'
  import { toPluralString } from '@/utilities/strings'

  const props = defineProps<{ flow: Flow }>()

  const route = inject(workspaceDashboardKey)!
  const injectedServices = useInjectedServices()

  const crumbs = [{ text: props.flow.name, to: '#' }]
  const recentFlowRunsFilters = computed<Required<Filter>[]>(() => [
    {
      object: 'flow',
      property: 'name',
      type: 'string',
      operation: 'equals',
      value: props.flow.name,
    },
    {
      object: 'flow_run',
      property: 'start_date',
      type: 'date',
      operation: 'newer',
      value: '1w',
    },
  ])

  const countFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const recentFlowRunsCountFilter = computed<UnionFilters>(() => ({
    ...countFilter.value,
    flow_runs: {
      expected_start_time: {
        after_: subWeeks(startOfToday(), 1).toISOString(),
      },
    },
  }))

  const recentFlowRunsCountSubscription = useSubscription(injectedServices.getFlowRunsCount, [recentFlowRunsCountFilter])
  const recentFlowRunsCount = computed(() => recentFlowRunsCountSubscription.response.value ?? 0)

  const deploymentsCountSubscription = useSubscription(injectedServices.getDeploymentsCount, [countFilter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response.value ?? 0)

  function openFlowPanel(): void {
    showPanel(FlowPanel, {
      flow: props.flow,
      dashboardRoute: route,
      openDeploymentPanel,
      ...injectedServices,
    })
  }

  function openDeploymentPanel(deployment: Deployment): void {
    showPanel(DeploymentPanel, {
      deployment,
      dashboardRoute: route,
      ...injectedServices,
    })
  }
</script>

<style lang="scss">
@use 'sass:map';

.flows-page-flow-list-item {
  text-align: left;
  display: grid;
  gap: var(--m-1);
  grid-template-areas: 'name'
                       'recent'
                       'details';

  @media only screen and (min-width: map.get($breakpoints, 'xs')) {
    grid-template-columns: 1fr 130px;
    grid-template-areas: 'name    recent'
                         'details details';
  }

  @media only screen and (min-width: map.get($breakpoints, 'sm')) {
    grid-template-areas: 'name    recent'
                         'details recent';
  }
}

.flows-page-flow-list-item__name {
  grid-area: name;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flows-page-flow-list-item__details {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--m-1);
  grid-area: details;
}

.flows-page-flow-list-item__recent {
  grid-area: recent;

  @media only screen and (min-width: map.get($breakpoints, 'xs')) {
    justify-self: end;
  }
}

.flows-page-flow-list-item__tags {
  overflow: hidden;
}
</style>