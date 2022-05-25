<template>
  <p-layout-default class="flow">
    <template #header>
      Flow {{ flowId }}

      <p-tabs :tabs="flowTabs">
        <template #deployments>
          <div v-for="deployment in flowDeployments" :key="deployment.id">
            {{ deployment }}
          </div>
        </template>
      </p-tabs>
    </template>

    <div>
      Flow Details
    </div>
    <div>
      {{ flowDetails }}
    </div>
    <FlowRunList v-model:selected="selectedFlowRuns" :flow-runs="flowRuns" disabled />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, FlowRunList } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowTabs = ['Deployments']

  const flowId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flowDetails = computed(() => flowSubscription.response ?? null)

  const flowFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))
  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [flowFilter])
  const flowRuns = computed(() => flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>