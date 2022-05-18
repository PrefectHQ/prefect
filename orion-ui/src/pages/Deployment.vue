<template>
  <div class="deployment">
    Deployment {{ deploymentId }}
  </div>

  <div>
    Deployment Details
  </div>
  <div>
    {{ deploymentDetails }}
  </div>

  <div>
    Deployment Flows
  </div>
  <div v-for="flow in deploymentFlows" :key="flow.id">
    {{ flow }}
  </div>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'


  const deploymentId = useRouteParam('id')
  const subscriptionOptions = {
    interval: 300000,
  }
  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deploymentDetails = computed(() => deploymentSubscription.response ?? [])

  const deploymentFlowFilter = computed<UnionFilters>(() => ({
    deployments: {
      id: {
        any_: [deploymentId.value],
      },
    },
  }))
  const deploymentFlowsSubscription = useSubscription(flowsApi.getFlows, [deploymentFlowFilter], subscriptionOptions)
  const deploymentFlows = computed(() => deploymentFlowsSubscription.response ?? [])
</script>

<style>
.deployment {}
</style>

