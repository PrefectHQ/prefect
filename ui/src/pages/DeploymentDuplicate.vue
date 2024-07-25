<template>
  <p-layout-default v-if="deployment" class="deployment-edit">
    <template #header>
      <PageHeadingDeploymentDuplicate :deployment="deployment" />
    </template>

    <DeploymentForm :deployment="deployment" mode="duplicate" @cancel="cancel" @submit="submit" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { PageHeadingDeploymentDuplicate, useWorkspaceApi, getApiErrorMessage, DeploymentForm, DeploymentCreate, DeploymentUpdateV2 } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import router, { routes } from '@/router'

  const api = useWorkspaceApi()
  const deploymentId = useRouteParam('deploymentId')

  const deploymentSubscription = useSubscription(api.deployments.getDeployment, [deploymentId.value], {})
  const deployment = computed(() => deploymentSubscription.response)

  function isDeploymentCreate(request: DeploymentCreate | DeploymentUpdateV2): request is DeploymentCreate {
    return 'name' in request
  }

  async function submit(request: DeploymentCreate | DeploymentUpdateV2): Promise<void> {
    try {
      if (!isDeploymentCreate(request)) {
        throw new Error('Invalid request')
      }
      const newDeployment = await api.deployments.createDeployment(request)
      showToast('Deployment created', 'success')
      router.push(routes.deployment(newDeployment.id))
    } catch (error) {
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

