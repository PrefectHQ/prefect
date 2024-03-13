<template>
  <p-layout-default class="deployment-edit">
    <template #header>
      <PageHeadingDeploymentEdit v-if="deployment" :deployment="deployment" />
    </template>

    <p-content v-if="deployment">
      <template v-if="can.access.schemasV2 && !useEnhancedDeploymentParameters">
        <p-message info>
          The enhanced deployment parameters UI improves support for lists, default values, validation, and more.
          <strong>If you're having trouble, please <p-link href="https://github.com/PrefectHQ/prefect/issues/new/choose">report an issue.</p-link></strong>
          <span> To revert to the previous deployment parameters UI click <p-link href="?useEnhancedDeploymentParameters=true" target="_self">here</p-link>.</span>
        </p-message>

        <DeploymentFormV2 :deployment="deployment" @cancel="cancel" @submit="submitV2" />
      </template>
      <template v-else>
        <template v-if="!useEnhancedDeploymentParameters">
          <p-message>
            <span>Enhanced deployment parameters UI improves support for lists, default values, validation, and more. Enable by updating your prefect config.</span>
            <p-code class="mt-2">
              prefect config PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_DEPLOYMENT_PARAMETERS=True
            </p-code>
          </p-message>
        </template>
        <template v-else>
          <p-message>
            <span>To use the enhanced deployment parameters UI click <p-link href="?useEnhancedDeploymentParameters=false" target="_self">here</p-link>. </span>
            <span>To disable the enhanced deployment parameters UI by default update your prefect config.</span>
            <p-code class="mt-2">
              prefect config PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_DEPLOYMENT_PARAMETERS=False
            </p-code>
          </p-message>
        </template>
        <DeploymentForm :deployment="deployment" @cancel="cancel" @submit="submit" />
      </template>
    </p-content>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { PageHeadingDeploymentEdit, DeploymentForm, DeploymentUpdate, useWorkspaceApi, useCan, DeploymentUpdateV2, getApiErrorMessage, DeploymentFormV2 } from '@prefecthq/prefect-ui-library'
  import { useSubscription, useRouteParam, useRouteQueryParam, BooleanRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import router, { routes } from '@/router'

  const api = useWorkspaceApi()
  const can = useCan()
  const useEnhancedDeploymentParameters = useRouteQueryParam('useEnhancedDeploymentParameters', BooleanRouteParam, false)
  const deploymentId = useRouteParam('deploymentId')
  const subscriptionOptions = {
    interval: 300000,
  }

  const deploymentSubscription = useSubscription(api.deployments.getDeployment, [deploymentId.value], subscriptionOptions)
  const deployment = computed(() => deploymentSubscription.response)

  async function submit(deployment: DeploymentUpdate): Promise<void> {
    try {
      await api.deployments.updateDeployment(deploymentId.value, deployment)
      showToast('Deployment updated', 'success')
      router.back()
    } catch (error) {
      showToast('Error updating deployment', 'error')
      console.warn(error)
    }
  }

  async function submitV2(request: DeploymentUpdateV2): Promise<void> {
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

