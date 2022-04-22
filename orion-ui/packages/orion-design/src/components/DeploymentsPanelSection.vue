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
          <template v-if="can?.create.flow_run">
            <m-button outlined class="text--grey-80" @click.stop="run(deployment)">
              Quick Run
            </m-button>
          </template>
        </button>
      </template>
    </template>
  </PanelSection>
</template>

<script lang="ts" setup>
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed, inject } from 'vue'
  import PanelSection from '@/components/PanelSection.vue'
  import { Deployment } from '@/models/Deployment'
  import { DeploymentsApi } from '@/services/DeploymentsApi'
  import { UnionFilters } from '@/services/Filter'
  import { canKey } from '@/types/permissions'
  import { showToast } from '@/utilities/toasts'

  const props = defineProps<{
    filter: UnionFilters,
    deploymentsApi: DeploymentsApi,
    openDeploymentPanel: (deployment: Deployment) => void,
  }>()

  const can = inject(canKey)

  const filter = computed(() => props.filter)

  const deploymentsCountSubscription = useSubscription(props.deploymentsApi.getDeploymentsCount, [filter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response ?? 0)

  const deploymentsSubscription = useSubscription(props.deploymentsApi.getDeployments, [filter])
  const deployments = computed(() => deploymentsSubscription.response ?? [])
  const noDeployments = computed(() => deploymentsSubscription.response?.length === 0)

  function run(deployment: Deployment): void {
    props.deploymentsApi.createDeploymentFlowRun(deployment.id, {
      state: {
        type: 'SCHEDULED',
        message: 'Quick run through UI',
      },
    })
      .catch(() => showToast('Failed to schedule flow run', 'error'))
      .then(() => showToast('Flow run scheduled', 'success'))
      .finally(() => deploymentsSubscription.refresh())
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
