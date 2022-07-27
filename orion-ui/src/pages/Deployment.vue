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
      <template #overview>
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
  import { DeploymentDescription, DeploymentDescriptionEmptyState, DeploymentDeprecatedMessage, PageHeadingDeployment, DeploymentDetails, ParametersTable } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { routes } from '@/router'
  import { deploymentsApi } from '@/services/deploymentsApi'

  const deploymentId = useRouteParam('id')
  const router = useRouter()

  const subscriptionOptions = {
    interval: 300000,
  }

  const tabs = computed(() => {
    const values = ['Overview', 'Parameters']

    if (!media.xl) {
      values.push('Details')
    }

    return values
  })


  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  function routeToDeployments(): void {
    router.push(routes.deployments())
  }
</script>
