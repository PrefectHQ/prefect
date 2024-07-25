<template>
  <p-layout-default v-if="deployment" class="deployment-edit">
    <template #header>
      <PageHeadingDeploymentEdit :deployment="deployment" />
    </template>

    <DeploymentForm :deployment="deployment" @cancel="cancel" @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { PageHeadingDeploymentEdit, useWorkspaceApi, DeploymentUpdateV2, getApiErrorMessage, DeploymentForm } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import router, { routes } from '@/router'

  const api = useWorkspaceApi()
  const deploymentId = useRouteParam('deploymentId')
  const subscriptionOptions = {
    interval: 300000,
  }

  const deploymentSubscription = useSubscription(api.deployments.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  async function submit(request: DeploymentUpdateV2): Promise<void> {
    try {
      await api.deployments.updateDeploymentV2(deploymentId.value, request)
      showToast('Deployment updated', 'success')
      deploymentSubscription.refresh()
      router.push(routes.deployment(deploymentId.value))
    } catch (error) {
      const message = getApiErrorMessage(error, 'Error updating deployment')
      showToast(message, 'error')
      console.warn(error)
    }
  }

  function cancel(): void {
    router.back()
  }

  const title = computed(() => {
    if (!deployment.value) {
      return 'Edit Deployment'
    }
    return `Edit Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)
</script>

