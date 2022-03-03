<template>
  <EmptyStateCard
    header="Create a flow to get started"
    description="Flows are the most basic Prefect object. They are containers for workflow logic and allow users to interact with and reason about the state of their workflows."
  >
    <a href="https://orion-docs.prefect.io/concepts/flows/" target="_blank">
      <m-button color="primary" miter icon="pi-add-line">
        View Docs
      </m-button>
    </a>
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
  import EmptyStateCard from './EmptyStateCard.vue'
  import FlowsPageFlowListItem from './FlowsPageFlowListItem.vue'
  import { getDeploymentsCountKey } from '@/services/DeploymentsApi'
  import { getFlowRunsCountKey } from '@/services/FlowRunsApi'
  import { mocker } from '@/services/Mocker'

  provide(getFlowRunsCountKey, () => Promise.resolve(mocker.create('number', [0, 15])))
  provide(getDeploymentsCountKey, () => Promise.resolve(mocker.create('number', [0, 3])))

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