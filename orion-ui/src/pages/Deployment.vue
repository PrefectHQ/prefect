<template>
  <p-layout-well class="deployment">
    <template #header>
      <PageHeadingDeployment v-if="deployment" :deployment="deployment" @delete="deleteDeployment" />
    </template>

    <p-tabs :tabs="['Overview', 'Parameters']">
      <template #overview>
        <template v-if="deployment">
          <div class="grid gap-2">
            <p-key-value label="Schedule" :value="schedule" />
            <p-key-value label="Location" :value="deployment.flowData.blob" />
            <p-key-value label="Flow Runner" :value="deployment.flowRunner" />
            <template v-if="!media.xl">
              <DeploymentDetails :deployment="deployment" />
            </template>
          </div>
        </template>
      </template>

      <template #parameters>
        <DeploymentParametersTable :parameters="deployment.parameters" />
      </template>
    </p-tabs>

    <template #well>
      <DeploymentDetails v-if="deployment" :deployment="deployment" />
    </template>
  </p-layout-well>
</template>

<script lang="ts" setup>
  import { useRouteParam, PageHeadingDeployment, DeploymentDetails, DeploymentParametersTable, mocker, formatSchedule } from '@prefecthq/orion-design'
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
  // const deployment = computed(() => deploymentSubscription.response)
  const deployment = computed(() => mocker.create('deployment'))

  const schedule = computed(() => formatSchedule(deployment.value.schedule))

  function deleteDeployment(): void {
    router.push(routes.deployments())
  }
</script>

