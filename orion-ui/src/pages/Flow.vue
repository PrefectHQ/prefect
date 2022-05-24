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
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowTabs = ['Deployments']

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