<template>
  <m-panel class="flow-panel">
    <template #title>
      <div class="flow-panel__title">
        <i class="pi pi-flow pi-sm flow-panel__icon" />
        <span class="ml-1">{{ flow.name }}</span>
      </div>
    </template>

    <div class="flow-panel__details">
      <DetailsKeyValue label="Created Date" :value="formatDateTimeNumericInTimeZone(flow.created)" stacked />
      <div class="flow-panel__id">
        <DetailsKeyValue label="Flow ID" :value="flow.id" class="text-truncate" stacked />
        <CopyButton :value="flow.id" label="Copy">
          <template #default />
        </CopyButton>
      </div>
      <DetailsKeyValue label="Tags" stacked>
        <m-tags :tags="flow.tags" />
      </DetailsKeyValue>
      <RecentFlowRunsPanelSection v-bind="{ baseFilter, dashboardRoute, flowRunsApi }" />
      <DeploymentsPanelSection v-bind="{ filter, openDeploymentPanel, dashboardRoute, deploymentsApi }" />
    </div>

    <template #actions="{ close }">
      <m-button @click="close">
        Close
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { RouteLocationRaw } from 'vue-router'
  import CopyButton from '@/components/CopyButton.vue'
  import DeploymentsPanelSection from '@/components/DeploymentsPanelSection.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import RecentFlowRunsPanelSection from '@/components/RecentFlowRunsPanelSection.vue'
  import { Deployment } from '@/models/Deployment'
  import { Flow } from '@/models/Flow'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { UnionFilters } from '@/services/Filter'
  import { FlowRunsApi } from '@/services/FlowRunsApi'
  import { Filter } from '@/types/filters'
  import { formatDateTimeNumericInTimeZone } from '@/utilities/dates'

  const props = defineProps<{
    flow: Flow,
    deploymentsApi: DeploymentsApi,
    flowRunsApi: FlowRunsApi,
    dashboardRoute: Exclude<RouteLocationRaw, string>,
    openDeploymentPanel: (deployment: Deployment) => void,
  }>()

  const filter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const baseFilter = computed<Required<Filter>>(() => ({
    object: 'flow',
    property: 'name',
    type: 'string',
    operation: 'equals',
    value: props.flow.name,
  }))
</script>

<style lang="scss">
.flow-panel__title {
  display: flex;
  align-items: center;
}

.flow-panel__icon {
  position: relative;
  top: 0.05em;
  color: var(--grey-40);
}

.flow-panel__details {
  display: grid;
  gap: var(--m-2);
}

.flow-panel__id {
  display: flex;
  justify-content: space-between;
  min-width: 0;
}

.flow-panel__count {
  font-weight: 400;
  font-family: var(--font-secondary);
  font-size: 13px;
  letter-spacing: -0.09px;
  line-height: 18px;
  text-align: center;
  color: var(--grey-80);
  border: 1px solid var(--secondary-hover);
  border-radius: 100px;
  min-width: 24px;
  display: inline-block;
}
</style>