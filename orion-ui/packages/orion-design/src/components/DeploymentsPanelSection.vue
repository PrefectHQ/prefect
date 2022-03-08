<template>
  <PanelSection icon="map-pin-line" full>
    <template #heading>
      <div class="deployments-panel-section__heading">
        Deployments
        <span class="flow-panel__count">{{ deploymentsCount }}</span>
      </div>
    </template>
    <template v-if="noDeployments">
      <div class="deployments-panel-section__empty">
        No Results
      </div>
    </template>
    <template v-else>
      <template v-for="deployment in deployments" :key="deployment.id">
        <button type="button" class="deployments-panel-section__deployment" @click="openDeploymentPanel(deployment)">
          <span class="deployment-panel-section__deployment-name">
            {{ deployment.name }}
          </span>
          <template v-if="!deployment.isScheduleActive">
            <span class="deployment-panel-section__deployment-paused">
              Paused
            </span>
          </template>
          <m-button color="alternate" @click.stop="run(deployment)">
            Quick Run
          </m-button>
        </button>
      </template>
    </template>
  </PanelSection>
</template>

<script lang="ts" setup>
  import { showToast } from '@prefecthq/miter-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { RouteLocationRaw } from 'vue-router'
  import DeploymentPanel from './DeploymentPanel.vue'
  import PanelSection from './PanelSection.vue'
  import { Deployment } from '@/models/Deployment'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { UnionFilters } from '@/services/Filter'
  import { FlowRunsApi } from '@/services/FlowRunsApi'
  import { ShowPanel } from '@/utilities/panels'

  const props = defineProps<{
    filter: UnionFilters,
    showPanel: ShowPanel,
    getFlowRunsCount: FlowRunsApi['getFlowRunsCount'],
    dashboardRoute: Exclude<RouteLocationRaw, string>,
    getDeployments: DeploymentsApi['getDeployments'],
    getDeploymentsCount: DeploymentsApi['getDeploymentsCount'],
    createDeploymentFlowRun: DeploymentsApi['createDeploymentFlowRun'],
    openDeploymentPanel: (deployment: Deployment) => void,
  }>()

  const filter = computed(() => props.filter)

  const deploymentsCountSubscription = useSubscription(props.getDeploymentsCount, [filter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response.value ?? 0)

  const deploymentsSubscription = useSubscription(props.getDeployments, [filter])
  const deployments = computed(() => deploymentsSubscription.response.value ?? [])
  const noDeployments = computed(() => deploymentsSubscription.response.value?.length === 0)

  function run(deployment: Deployment): void {
    props.createDeploymentFlowRun(deployment.id, {
      state: {
        type: 'SCHEDULED',
        message: 'Quick run through UI',
      },
    })
      .catch(() => showToast('Failed to schedule flow run', 'error'))
      .then(() => showToast('Flow run scheduled'))
      .finally(() => deploymentsSubscription.refresh())
  }

  function openDeploymentPanel(deployment: Deployment): void {
    props.showPanel(DeploymentPanel, {
      deployment,
      getFlowRunsCount: props.getFlowRunsCount,
      dashboardRoute: props.dashboardRoute,
    })
  }
</script>

<style lang="scss">
.deployments-panel-section__heading {
  display: flex;
  align-items: center;
  gap: var(--m-1);
}

.deployments-panel-section__deployment {
  display: flex;
  justify-content: space-between;
  padding: var(--panel-padding);
  align-items: center;
  gap: var(--m-1);
  width: 100%;
  border: 0;
  background: none;
  border-top: 1px solid var(--secondary-hover);
  cursor: pointer;

  &:hover {
    color: var(--primary-hover);
  }
}

.deployment-panel-section__deployment-name {
  font-size: 16px;
  font-weight: 24px;
}

.deployment-panel-section__deployment-paused {
  margin-left: auto;
  font-size: 13px;
  line-height: 24px;
  color: var(--grey-80);
  border: 1px solid var(--secondary-hover);
  border-radius: 4px;
  padding: 0 var(--p-1);
}

.deployments-panel-section__empty {
  padding-left: var(--panel-padding);
}
</style>
