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
        <DeploymentsTable :filter="deploymentsFilter" />
      </template>

      <template #runs>
        <FlowRunFilteredList :flow-run-filter="flowRunsFilter" />
      </template>
    </p-tabs>

    <template #well>
      <FlowDetails v-if="flow" :flow="flow" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { DeploymentsTable, PageHeadingFlow, FlowDetails, FlowRunFilteredList, useWorkspaceApi, useRecentFlowRunsFilter, useDeploymentsFilter } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router/routes'

  const api = useWorkspaceApi()
  const flowId = useRouteParam('flowId')
  const flowIds = computed(() => [flowId.value])
  const router = useRouter()
  const tabs = computed(() => {
    const values = ['Runs', 'Deployments']

    if (!media.xl) {
      values.unshift('Details')
    }

    return values
  })

  const subscriptionOptions = {
    interval: 300000,
  }

  const flowSubscription = useSubscription(api.flows.getFlow, [flowId.value], subscriptionOptions)
  const flow = computed(() => flowSubscription.response)

  const { filter: flowRunsFilter } = useRecentFlowRunsFilter({
    flows: {
      id: flowIds,
    },
  })

  const { filter: deploymentsFilter } = useDeploymentsFilter({
    flows: {
      id: flowIds,
    },
  })

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