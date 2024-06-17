<template>
  <p-layout-default class="flow">
    <template #header>
      <PageHeadingFlow v-if="flow" :flow="flow" @delete="deleteFlow" />
    </template>

    <FlowStats v-if="flow" :flow-id="flow.id" />

    <p-tabs v-model:selected="tab" :tabs="tabs">
      <template #details>
        <FlowDetails v-if="flow" :flow="flow" />
      </template>

      <template #deployments>
        <DeploymentList :filter="deploymentsFilter" prefix="deployments" />
      </template>

      <template #runs>
        <FlowRunFilteredList :filter="flowRunsFilter" selectable prefix="runs" />
      </template>
    </p-tabs>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { DeploymentList, PageHeadingFlow, FlowDetails, FlowRunFilteredList, useWorkspaceApi, useFlowRunsFilter, useDeploymentsFilter } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import FlowStats from '@/components/FlowStats.vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router/routes'

  const api = useWorkspaceApi()
  const flowId = useRouteParam('flowId')
  const flowIds = computed(() => [flowId.value])
  const router = useRouter()
  const tab = useRouteQueryParam('tab', 'Runs')
  const tabs = ['Runs', 'Deployments', 'Details']

  const subscriptionOptions = {
    interval: 300000,
  }

  const flowSubscription = useSubscription(api.flows.getFlow, [flowId.value], subscriptionOptions)
  const flow = computed(() => flowSubscription.response)

  const { filter: flowRunsFilter } = useFlowRunsFilter({
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