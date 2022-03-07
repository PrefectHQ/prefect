<template>
  <m-panel>
    <template #title>
      <div class="flow-panel__title">
        <i class="pi pi-flow pi-sm flow-panel__icon" />
        <span class="ml-1">{{ flow.name }}</span>
      </div>
    </template>

    <div class="flow-panel__details">
      <DetailsKeyValue label="Created Date" :value="formatDateTimeNumeric(flow.created)" stacked />
      <div class="flow-panel__id">
        <DetailsKeyValue label="Flow ID" :value="flow.id" stacked />
        <CopyButton :value="flow.id" label="Copy">
          <template #default />
        </CopyButton>
      </div>
      <DetailsKeyValue label="Tags" stacked>
        <m-tags :tags="flow.tags" />
      </DetailsKeyValue>
    </div>

    <PanelSection icon="map-pin-line">
      <template #heading>
        <div class="flow-panel__deployments-heading">
          Deployments
          <span class="flow-panel__count">{{ deploymentsCount }}</span>
        </div>
      </template>
      <template v-if="noDeployments">
        No Results
      </template>
      <template v-else>
        <template v-for="deployment in deployments" :key="deployment.id">
          {{ deployment.name }}
        </template>
      </template>
    </PanelSection>

    <template #actions="{ close }">
      <m-button @click="close">
        Close
      </m-button>
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import CopyButton from './CopyButton.vue'
  import DetailsKeyValue from './DetailsKeyValue.vue'
  import { Flow } from '@/models/Flow'
  import { formatDateTimeNumeric } from '@/utilities/dates'
  import PanelSection from './PanelSection.vue'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { inject, computed } from 'vue'
  import { getDeploymentsCountKey, getDeploymentsKey, deploymentsApi } from '@/services/DeploymentsApi'
import { UnionFilters } from '@/services/Filter'

  const props = defineProps<{
    flow: Flow,
  }>()

  const deploymentsFilter = computed<UnionFilters>(() => ({
    flows: {
      id: {
        any_: [props.flow.id],
      },
    },
  }))

  const getDeploymentsCount = inject(getDeploymentsCountKey, deploymentsApi.getDeploymentsCount)
  const deploymentsCountSubscription = useSubscription(getDeploymentsCount, [deploymentsFilter])
  const deploymentsCount = computed(() => deploymentsCountSubscription.response.value ?? 0)

  const getDeployments = inject(getDeploymentsKey, deploymentsApi.getDeployments)
  const deploymentsSubscription = useSubscription(getDeployments, [deploymentsFilter])
  const deployments = computed(() => deploymentsSubscription.response.value ?? [])
  const noDeployments = computed(() => deploymentsSubscription.response.value?.length === 0)
</script>

<style lang="scss">
.flow-panel__title {
  display: flex;
  align-items: center;
}

.flow-panel__icon {
  position: relative;
  top: 0.05em;
  color: var(--grey-40);
}

.flow-panel__details {
  display: grid;
  gap: var(--m-2);
}

.flow-panel__id {
  display: flex;
  justify-content: space-between;
  min-width: 0;
}

.flow-panel__deployments-heading {
  display: flex;
  align-items: center;
  gap: var(--m-1);
}

.flow-panel__count {
  font-weight: 400;
  font-family: var(--font-secondary);
  font-size: 13px;
  letter-spacing: -0.09px;
  line-height: 18px;
  text-align: center;
  color: var(--grey-80);
  border: 1px solid var(--secondary-hover);
  border-radius: 100px;
  min-width: 24px;
  display: inline-block;
}
</style>