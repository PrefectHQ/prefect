<template>
  <p-layout-default v-if="deployment">
    <template #header>
      <PageHeadingFlowRunCreate :deployment="deployment" />
    </template>

    <FlowRunCreateFormV2 :deployment="deployment" :parameters="parameters" @submit="createFlowRun" @cancel="goBack" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/prefect-design'
  import { PageHeadingFlowRunCreate, ToastFlowRunCreate, useWorkspaceApi, useDeployment, FlowRunCreateFormV2, DeploymentFlowRunCreateV2, getApiErrorMessage } from '@prefecthq/prefect-ui-library'
  import { useRouteParam, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import { computed, h } from 'vue'
  import { useRouter } from 'vue-router'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { routes } from '@/router'
  import { JSONRouteParam } from '@/utilities/parameters'

  const api = useWorkspaceApi()
  const deploymentId = useRouteParam('deploymentId')
  const router = useRouter()
  const parameters = useRouteQueryParam('parameters', JSONRouteParam, undefined)
  const { deployment } = useDeployment(deploymentId)

  const createFlowRun = async (request: DeploymentFlowRunCreateV2): Promise<void> => {
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