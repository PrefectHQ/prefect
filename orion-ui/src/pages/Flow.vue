<template>
  <p-layout-well class="flow">
    <template #header>
      <PageHeadingFlow v-if="flow" :flow="flow" @delete="deleteFlow" />
    </template>

    <p-tabs :tabs="tabs">
      <template #details>
        <FlowDetails v-if="flow" :flow="flow" />
      </template>
      <template #deployments>
        <DeploymentsTable :deployments="flowDeployments" @delete="flowDeploymentsSubscription.refresh()" />
      </template>
    </p-tabs>

    <template #well>
      <FlowDetails v-if="flow" :flow="flow" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useRouteParam, UnionFilters, DeploymentsTable, PageHeadingFlow, FlowDetails } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router/routes'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowId = useRouteParam('id')
  const router = useRouter()
  const tabs = computed(() => {
    const tabs = ['Deployments']

    if (!media.xl) {
      tabs.unshift('Details')
    }

    return tabs
  })

  const subscriptionOptions = {
    interval: 300000,
  }

  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flow = computed(() => flowSubscription.response)

  const flowDeploymentFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))

  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowDeploymentFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])

  function deleteFlow(): void {
    router.push(routes.flows())
  }
</script>