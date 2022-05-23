<template>
  <p-layout-default class="flow">
    <template #header>
      Flow {{ flowId }}
    </template>

    <div>
      Flow Details
    </div>
    <div>
      {{ flowDetails }}
    </div>

    <div>
      Flow Deployments
    </div>
    <div v-for="deployment in flowDeployments" :key="deployment.id">
      {{ deployment }}
    </div>

    <p>Flow Sub Runs</p>
    <FlowRunList :flow-runs="flowRuns" :selected="selectedFlowRuns" disabled />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, FlowRunList } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, ref } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flowDetails = computed(() => flowSubscription.response ?? [])

  const flowFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))
  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])

  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [flowFilter], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])
</script>