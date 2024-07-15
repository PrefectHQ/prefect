<template>
  <p-layout-default v-if="deployment" class="deployment-edit">
    <template #header>
      <PageHeadingDeploymentDuplicate :deployment="deployment" />
    </template>

    <DeploymentFormV2 :deployment="deployment" @cancel="cancel" :can-update-name="true" @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { PageHeadingDeploymentDuplicate, useWorkspaceApi, DeploymentUpdateV2, getApiErrorMessage, DeploymentFormV2, DeploymentCreate } from '@prefecthq/prefect-ui-library'
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
      const deploymentRequest: DeploymentCreate = {
        ...deployment.value, 
        ...request,
      }
      const newDeployment = await api.deployments.createDeployement(deploymentRequest)
      showToast('Deployment created', 'success')
      router.push(routes.deployment(newDeployment.id))
    } catch (error) {
      debugger
      const message = getApiErrorMessage(error, 'Error creating deployment')
      showToast(message, 'error')
      console.warn(error)
    }
  }

  function cancel(): void {
    router.back()
  }

  const title = computed(() => {
    if (!deployment.value) {
      return 'Duplicate Deployment'
    }
    return `Duplicate Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)
</script>

