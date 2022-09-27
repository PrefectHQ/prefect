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
        <FlowRunsControlsList :flow-run-filter="flowFilter" />
      </template>
    </p-tabs>

    <template #well>
      <FlowDetails v-if="flow" :flow="flow" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { DeploymentsTable, PageHeadingFlow, FlowDetails, FlowRunsControlsList, UnionFilters, useRecentFlowRunFilter, useFlowRunFilterFromRoute } from '@prefecthq/orion-design'
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

  const { states, sort } = useFlowRunFilterFromRoute()

  const flowFilter = useRecentFlowRunFilter({ flows: [flowId.value], states, sort })
  const flowFilterArgs = computed<[filter: UnionFilters] | null>(() => flowId.value ? [flowFilter.value] : null)

  const flowDeploymentsSubscription = useSubscriptionWithDependencies(deploymentsApi.getDeployments, flowFilterArgs)
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