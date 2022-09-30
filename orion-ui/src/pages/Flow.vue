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
        <DeploymentsTable :deployments="flowDeployments" @update="flowDeploymentsSubscription.refresh()" @delete="flowDeploymentsSubscription.refresh()" />
      </template>

      <template #runs>
        <FlowRunFilteredList :flow-run-filter="flowFilter" />
      </template>
    </p-tabs>

    <template #well>
      <FlowDetails v-if="flow" :flow="flow" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { DeploymentsTable, PageHeadingFlow, FlowDetails, FlowRunFilteredList, UnionFilters, useRecentFlowRunFilter } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam, useSubscriptionWithDependencies } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router/routes'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowsApi } from '@/services/flowsApi'

  const flowId = useRouteParam('id')
  const router = useRouter()
  const tabs = computed(() => {
    const values = ['Deployments', 'Runs']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const subscriptionOptions = {
    interval: 300000,
  }

  const flowSubscription = useSubscription(flowsApi.getFlow, [flowId.value], subscriptionOptions)
  const flow = computed(() => flowSubscription.response)

  const flowFilter = useRecentFlowRunFilter({ flows: [flowId.value] })

  const flowDeploymentFilterArgs = computed<[filter: UnionFilters] | null>(() => {
    if (!flowId.value) {
      return null
    }
    return [
      {
        flows: {
          id: {
            any_: [flowId.value],
          },
        },
      },
    ]
  })

  const flowDeploymentsSubscription = useSubscriptionWithDependencies(deploymentsApi.getDeployments, flowDeploymentFilterArgs)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])
  function deleteFlow(): void {
    router.push(routes.flows())
  }

  const title = computed(() => {
    if (!flow.value) {
      return 'Flow'
    }
    return `Flow: ${flow.value.name}`
  })
  usePageTitle(title)
</script>