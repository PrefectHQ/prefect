<template>
  <p-layout-well class="deployment">
    <template #header>
      <PageHeadingDeployment v-if="deployment" :deployment="deployment" @update="deploymentSubscription.refresh" @delete="routeToDeployments" />
    </template>

    <p-tabs v-if="deployment" :tabs="['Overview', 'Parameters']">
      <template #overview>
        <div class="grid gap-2">
          <p-key-value label="Schedule" :value="schedule" />
          <p-key-value label="Location" :value="deployment.flowData.blob" />
          <p-key-value label="Flow Runner" :value="deployment.flowRunner?.type" />
          <template v-if="!media.xl">
            <DeploymentDetails :deployment="deployment" />
          </template>
        </div>
      </template>

      <template #parameters>
        <DeploymentParametersTable :parameters="deployment.parameters" />
      </template>
    </p-tabs>

    <template #well>
      <DeploymentDetails v-if="deployment" :deployment="deployment" alternate />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useRouteParam, PageHeadingDeployment, DeploymentDetails, DeploymentParametersTable, formatSchedule } from '@prefecthq/orion-design'
  import { media } from '@prefecthq/prefect-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
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

  const schedule = computed(() => deployment.value ? formatSchedule(deployment.value.schedule) : '')

  function routeToDeployments(): void {
    router.push(routes.deployments())
  }
</script>

