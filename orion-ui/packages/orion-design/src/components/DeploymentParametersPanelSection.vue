<template>
  <PanelSection class="deployment-parameters-panel-section" icon="settings-4-line" full>
    <template #heading>
      <div class="deployment-parameters-panel-section__heading">
        <span>Parameters</span>
        <CopyButton label="Copy" :value="parametersCsv">
          <template #default />
        </CopyButton>
      </div>
    </template>
    <template v-if="noParameters">
      <div class="deployments-panel-section__empty">
        No Results
      </div>
    </template>
    <template v-else>
      <template v-for="(value, key) in parameters" :key="key">
        <div class="deployment-parameters-panel-section__parameter">
          <DetailsKeyValue :label="key" :value="value" stacked />
        </div>
      </template>
    </template>
  </PanelSection>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import CopyButton from '@/components/CopyButton.vue'
  import DetailsKeyValue from '@/components/DetailsKeyValue.vue'
  import PanelSection from '@/components/PanelSection.vue'
  import { Deployment } from '@/models/Deployment'

  const props = defineProps<{
    parameters: Deployment['parameters'],
  }>()

  const noParameters = computed(() => Object.keys(props.parameters).length === 0)

  const parametersCsv = (): string => {
    return Object.keys(props.parameters)
      .map(key => `${key}\t${props.parameters[key]}`)
      .join('\n')
  }
</script>

<style lang="scss">
.deployment-parameters-panel-section__heading {
  display: flex;
  justify-content: space-between;
}

.deployment-parameters-panel-section__parameter {
  padding: var(--panel-padding);
  border-top: 1px solid var(--secondary-hover);
}
</style>
