<template>
  <p-layout-well class="deployment">
    <template #header>
      <PageHeadingDeployment
        v-if="deployment"
        :deployment="deployment"
        @update="deploymentSubscription.refresh"
        @delete="routeToDeployments"
      />
    </template>

    <p-tabs v-if="deployment" :tabs="tabs">
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

      <template #details>
        <DeploymentDetails :deployment="deployment" @update="deploymentSubscription.refresh" />
      </template>

      <template #runs>
        <FlowRunFilteredList :flow-run-filter="deploymentFilter" />
      </template>
    </p-tabs>

    <template #well>
      <DeploymentDetails
        v-if="deployment"
        :deployment="deployment"
        alternate
        @update="deploymentSubscription.refresh"
      />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { DeploymentDescription, FlowRunFilteredList, DeploymentDescriptionEmptyState, DeploymentDeprecatedMessage, PageHeadingDeployment, DeploymentDetails, ParametersTable, localization, useRecentFlowRunFilter, useTabs, useWorkspaceApi } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useToast } from '@/compositions'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'

  const deploymentId = useRouteParam('id')
  const router = useRouter()
  const api = useWorkspaceApi()
  const showToast = useToast()

  const subscriptionOptions = {
    interval: 300000,
  }

  const computedTabs = computed(() => [
    { label: 'Details', hidden: media.xl },
    { label: 'Description' },
    { label: 'Runs' },
    { label: 'Parameters', hidden: deployment.value?.deprecated },
  ])
  const tabs = useTabs(computedTabs)

  const deploymentSubscription = useSubscription(api.deployments.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  function routeToDeployments(): void {
    router.push(routes.deployments())
  }

  const deploymentFilter = useRecentFlowRunFilter({ deployments: [deploymentId.value] })

  const title = computed(() => {
    if (!deployment.value) {
      return 'Deployment'
    }
    return `Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)

  watch(deployment, () => {
    // If the deployment isn't deprecated and doesn't have a work queue, show the missing work queue message
    if (!deployment.value?.workQueueName && !deployment.value?.deprecated) {
      showToast(localization.info.deploymentMissingWorkQueue, 'default', { timeout: false })
    }
  })
</script>
