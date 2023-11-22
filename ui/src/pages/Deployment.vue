<template>
  <p-layout-well v-if="deployment" class="deployment">
    <template #header>
      <PageHeadingDeployment
        :deployment="deployment"
        @update="deploymentSubscription.refresh"
        @delete="routeToDeployments"
      />
    </template>

    <DeploymentStats v-if="deployment" :deployment-id="deployment.id" />

    <p-tabs v-model:selected="tab" :tabs="tabs">
      <template #description>
        <p-content secondary>
          <DeploymentDeprecatedMessage v-if="deployment.deprecated" />
          <template v-else-if="deployment.description">
            <DeploymentDescription :description="deployment.description" />
          </template>
          <template v-else>
            <DeploymentDescriptionEmptyState :deployment="deployment" />
          </template>
        </p-content>
      </template>

      <template #parameters>
        <ParametersTable :deployment="deployment" />
      </template>

      <template #configuration>
        <DeploymentConfiguration :deployment="deployment" />
      </template>

      <template #details>
        <DeploymentDetails :deployment="deployment" @update="deploymentSubscription.refresh" />
      </template>

      <template #runs>
        <FlowRunFilteredList :filter="deploymentFilter" prefix="runs" />
      </template>
    </p-tabs>

    <template #well>
      <DeploymentDetails :deployment="deployment" alternate @update="deploymentSubscription.refresh" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { media } from '@prefecthq/prefect-design'
  import { DeploymentDescription, FlowRunFilteredList, DeploymentDescriptionEmptyState, DeploymentDeprecatedMessage, PageHeadingDeployment, DeploymentDetails, ParametersTable, useTabs, useWorkspaceApi, useFlowRunsFilter, DeploymentConfiguration } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import DeploymentStats from '@/components/DeploymentStats.vue'

  const deploymentId = useRouteParam('deploymentId')
  const deploymentIds = computed(() => [deploymentId.value])
  const router = useRouter()
  const api = useWorkspaceApi()

  const subscriptionOptions = {
    interval: 300000,
  }

  const deploymentSubscription = useSubscription(api.deployments.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  const computedTabs = computed(() => [
    { label: 'Details', hidden: media.xl },
    { label: 'Runs' },
    { label: 'Parameters', hidden: deployment.value?.deprecated },
    { label: 'Configuration', hidden: deployment.value?.deprecated },
    { label: 'Description' },
  ])
  const tab = useRouteQueryParam('tab', 'Details')
  const { tabs } = useTabs(computedTabs, tab)

  function routeToDeployments(): void {
    router.push(routes.deployments())
  }

  const { filter: deploymentFilter } = useFlowRunsFilter({
    deployments: {
      id: deploymentIds,
    },
  })


  const title = computed(() => {
    if (!deployment.value) {
      return 'Deployment'
    }
    return `Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)
</script>

<style>
.deployment__infra-overrides { @apply
  px-4
  py-3
}
</style>