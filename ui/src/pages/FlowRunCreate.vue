<template>
  <p-layout-default v-if="deployment">
    <template #header>
      <PageHeadingFlowRunCreate :deployment="deployment" />
    </template>

    <template v-if="can.access.schemasV2 && !useEnhancedDeploymentParameters">
      <p-message info>
        The enhanced deployment parameters UI improves support for lists, default values, validation, and more.
        <strong>If you're having trouble, please <p-link href="https://github.com/PrefectHQ/prefect/issues/new/choose">report an issue.</p-link></strong>
        <span> To revert to the previous deployment parameters UI click <p-link href="?useEnhancedDeploymentParameters=true" target="_self">here</p-link>.</span>
      </p-message>
      <FlowRunCreateFormV2 :deployment="deployment" :parameters="parameters" @submit="createFlowRunV2" @cancel="goBack" />
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
      <FlowRunCreateForm :deployment="deployment" :parameters="parameters" @submit="createFlowRun" @cancel="goBack" />
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { FlowRunCreateForm, PageHeadingFlowRunCreate, DeploymentFlowRunCreate, ToastFlowRunCreate, useWorkspaceApi, useDeployment, FlowRunCreateFormV2, useCan, DeploymentFlowRunCreateV2, getApiErrorMessage } from '@prefecthq/prefect-ui-library'
  import { BooleanRouteParam, useRouteParam, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import { computed, h } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { JSONRouteParam } from '@/utilities/parameters'

  const api = useWorkspaceApi()
  const can = useCan()
  const deploymentId = useRouteParam('deploymentId')
  const router = useRouter()
  const parameters = useRouteQueryParam('parameters', JSONRouteParam, undefined)
  const { deployment } = useDeployment(deploymentId)
  const useEnhancedDeploymentParameters = useRouteQueryParam('useEnhancedDeploymentParameters', BooleanRouteParam, false)

  const createFlowRun = async (deploymentFlowRun: DeploymentFlowRunCreate): Promise<void> => {
    try {
      const flowRun = await api.deployments.createDeploymentFlowRun(deploymentId.value, deploymentFlowRun)
      const startTime = deploymentFlowRun.state?.stateDetails?.scheduledTime ?? undefined
      const immediate = !startTime
      const toastMessage = h(ToastFlowRunCreate, { flowRun, flowRunRoute: routes.flowRun, router, immediate, startTime })
      showToast(toastMessage, 'success')
      router.push(routes.deployment(deploymentId.value))
    } catch (error) {
      showToast('Something went wrong trying to create a flow run', 'error')
      console.error(error)
    }
  }

  const createFlowRunV2 = async (request: DeploymentFlowRunCreateV2): Promise<void> => {
    try {
      const flowRun = await api.deployments.createDeploymentFlowRunV2(deploymentId.value, request)
      const startTime = request.state?.stateDetails?.scheduledTime ?? undefined
      const immediate = !startTime
      const toastMessage = h(ToastFlowRunCreate, { flowRun, flowRunRoute: routes.flowRun, router, immediate, startTime })
      showToast(toastMessage, 'success')
      router.push(routes.deployment(deploymentId.value))
    } catch (error) {
      const message = getApiErrorMessage(error, 'Something went wrong trying to create a flow run')
      showToast(message, 'error')
      console.error(error)
    }
  }

  const goBack = (): void => {
    router.back()
  }

  const title = computed<string>(() => {
    if (!deployment.value) {
      return 'Create Flow Run for Deployment'
    }
    return `Create Flow Run for Deployment: ${deployment.value.name}`
  })
  usePageTitle(title)
</script>