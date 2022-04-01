<template>
  <ListItem class="flows-page-flow-list-item">
    <div class="flows-page-flow-list-item__name">
      <BreadCrumbs :crumbs="crumbs" tag="h2" />
    </div>

    <div class="flows-page-flow-list-item__details">
      <m-tag icon="pi-map-pin-line" flat>
        {{ deploymentsCount.toLocaleString() }}
        {{ toPluralString('Deployment', deploymentsCount) }}
      </m-tag>
      <m-tags class="flows-page-flow-list-item__tags" :tags="flow.tags" />
    </div>
    <slot name="flow-filters">
      <FlowRecentRunsFilterButton class="flows-page-flow-list-item__recent" :flow="flow" />
    </slot>
  </ListItem>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, inject } from 'vue'
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import DeploymentPanel from '@/components/DeploymentPanel.vue'
  import FlowPanel from '@/components/FlowPanel.vue'
  import FlowRecentRunsFilterButton from '@/components/FlowRecentRunsFilterButton.vue'
  import ListItem from '@/components/ListItem.vue'
  import { useInjectedServices } from '@/compositions/useInjectedServices'
  import { Crumb } from '@/models/Crumb'
  import { Deployment } from '@/models/Deployment'
  import { Flow } from '@/models/Flow'
  import { workspaceDashboardKey } from '@/router/routes'
  import { UnionFilters } from '@/services/Filter'
  import { showPanel } from '@/utilities/panels'
  import { toPluralString } from '@/utilities/strings'

  const props = defineProps<{ flow: Flow }>()

  const route = inject(workspaceDashboardKey)!
  const injectedServices = useInjectedServices()

  const crumbs: Crumb[] = [{ text: props.flow.name, action: openFlowPanel }]

  const countFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const deploymentsCountSubscription = useSubscription(injectedServices.getDeploymentsCount, [countFilter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response ?? 0)

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
  align-items: center;
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

.flows-page-flow-list-item__recent {
  grid-area: recent;

  @media only screen and (min-width: map.get($breakpoints, 'xs')) {
    justify-self: end;
  }
}

.flows-page-flow-list-item__details {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--m-1);
  grid-area: details;
}

.flows-page-flow-list-item__tags {
  overflow: hidden;
}
</style>