<template>
  <p-layout class="flow">
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
  </p-layout>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flowDetails = computed(() => flowSubscription.response ?? [])

  const flowDeploymentFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))
  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowDeploymentFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])
</script>