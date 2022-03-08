<template>
  <div class="deployments-multi-select">
    <template v-if="deployments.length">
      <m-data-table :rows="deployments" :columns="deploymentColumns">
        <template #column-actions="{ row }">
          <m-checkbox :value="selectedDeploymentIds.includes(row.id)" :label="row.name" @update:model-value="updateSelected(row.id, $event)" />
        </template>
      </m-data-table>
    </template>
    <template v-else>
      <div class="deployments-multi-select__empty-message">
        No Deployments Found
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { PropType } from 'vue'
  import { Deployment } from '@/models/Deployment'

  const props = defineProps({
    deployments: {
      type: Object as PropType<Deployment[]>,
      required: true,
    },
    selectedDeploymentIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  })

  const emit = defineEmits<{
    (event: 'update:selectedDeploymentIds', value: string[]): void,
  }>()

  const deploymentColumns =  [
    {
      label: 'Select',
      value: 'actions',
      search: false,
    },
    {
      label: 'Name',
      value: 'name',
      search: true,
    },
  ]

  const updateSelected = (id: string, selected: boolean): void => {
    if (selected && !props.selectedDeploymentIds.includes(id)) {
      emit('update:selectedDeploymentIds', [...props.selectedDeploymentIds, id])
    } else if (!selected && props.selectedDeploymentIds.includes(id)) {
      emit('update:selectedDeploymentIds', [...props.selectedDeploymentIds].filter(deploymentId => deploymentId !== id))
    }
  }
</script>

<style lang="scss">
.deployments-multi-select__empty-message{
  padding: var(--p-2) 0;
}
</style>