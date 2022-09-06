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
        <FlowRunList v-if="flowRuns.length" :flow-runs="flowRuns" disabled :selected="selectedFlowRuns" />
        <PEmptyResults v-else>
          <template #message>
            No runs from the last 7 days
          </template>
        </PEmptyResults>
      </template>
    </p-tabs>

    <template #well>
      <FlowDetails v-if="flow" :flow="flow" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { UnionFilters, DeploymentsTable, PageHeadingFlow, FlowDetails, FlowRunList, useFlowRunFilterFromParam } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, ref, Ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router/routes'
  import { deploymentsApi } from '@/services/deploymentsApi'
  import { flowRunsApi } from '@/services/flowRunsApi'
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

  const flowDeploymentFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [flowId.value],
      },
    },
  }))

  const flowDeploymentsSubscription = useSubscription(deploymentsApi.getDeployments, [flowDeploymentFilter], subscriptionOptions)
  const flowDeployments = computed(() => flowDeploymentsSubscription.response ?? [])

  const flows: Ref<string[]> = ref<string[]>([flowId.value])
  const filter =  useFlowRunFilterFromParam({ flows: flows.value })
  console.log('filter on flow page', filter.filter)
  const flowRunsSubscription = useSubscription(flowRunsApi.getFlowRuns, [filter.filter.value], subscriptionOptions)
  const flowRuns = computed(()=> flowRunsSubscription.response ?? [])
  const selectedFlowRuns = ref([])

  function deleteFlow(): void {
    router.push(routes.flows())
  }
</script>