<template>
  <EmptyStateCard
    header="Create a flow to get started"
    description="Flows are the most basic Prefect object. They are containers for workflow logic and allow users to interact with and reason about the state of their workflows."
  >
    <template v-if="hideDocsButton">
      <a href="https://orion-docs.prefect.io/concepts/flows/" target="_blank">
        <m-button color="primary" miter icon="pi-add-line">
          View Docs
        </m-button>
      </a>
    </template>
    <template #example>
      <div class="flows-page-flow-list-empty-state__example">
        <template v-for="flow in flows" :key="flow.id">
          <FlowsPageFlowListItem :flow="flow" />
        </template>
      </div>
    </template>
  </EmptyStateCard>
</template>

<script lang="ts" setup>
  import { provide } from 'vue'
  import EmptyStateCard from '@/components/EmptyStateCard.vue'
  import FlowsPageFlowListItem from '@/components/FlowsPageFlowListItem.vue'
  import { DeploymentsApi, deploymentsApiKey } from '@/services/DeploymentsApi'
  import { FlowRunsApi, flowRunsApiKey } from '@/services/FlowRunsApi'
  import { mocker } from '@/services/Mocker'

  defineProps<{
    hideDocsButton?: boolean,
  }>()

  // these mock the count endpoints for the FlowsPageFlowListItem
  // "as unknown as" is used so we don't have to mock the whole service
  provide(flowRunsApiKey, {
    getFlowRunsCount: () => Promise.resolve(mocker.create('number', [0, 15])),
  } as unknown as FlowRunsApi)

  provide(deploymentsApiKey, {
    getDeploymentsCount: () => Promise.resolve(mocker.create('number', [0, 3])),
  } as unknown as DeploymentsApi)

  const flows = [
    mocker.create('flow', [{ name: 'My-ETL-Flow', tags: [] }]),
    mocker.create('flow', [{ name: 'DS-Staging-Flow', tags: ['Apollo, DevOps, Staging'] }]),
    mocker.create('flow', [{ name: 'Q4-Prod-Flow', tags: ['Apollo, DevOps, Production'] }]),
  ]
</script>

<style lang="scss">
.flows-page-flow-list-empty-state__example {
  max-width: 700px;
  min-width: 400px;
  margin: 0 auto;
  pointer-events: none;
}
</style>