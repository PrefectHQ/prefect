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

    <p-tabs v-if="deployment" :tabs="['Overview', 'Parameters']">
      <template #overview>
        <p-content secondary>
          <template v-if="deployment.description">
            <DeploymentDescription :description="deployment.description" />
          </template>
          <template v-else>
            <DeploymentDescriptionEmptyState :deployment="deployment" />
          </template>

          <template v-if="!media.xl">
            <DeploymentDetails :deployment="deployment" />
          </template>
        </p-content>
      </template>

      <template #parameters>
        <ParametersTable :parameters="deployment.parameters" />
      </template>
    </p-tabs>

    <template #well>
      <DeploymentDetails v-if="deployment" :deployment="deployment" alternate />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { DeploymentDescription, DeploymentDescriptionEmptyState, PageHeadingDeployment, DeploymentDetails, ParametersTable } from '@prefecthq/orion-design'
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

  const deploymentSubscription = useSubscription(deploymentsApi.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  function routeToDeployments(): void {
    router.push(routes.deployments())
  }
</script>
