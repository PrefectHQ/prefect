<template>
  <p-select v-model="type" :options="options" class="automation-action-type-select" />
</template>

<script lang="ts" setup>
  import { SelectOption } from '@prefecthq/prefect-design'
  import { AutomationActionType, automationActionTypeLabels, automationActionTypes } from '@prefecthq/prefect-ui-library'
  import { computed } from 'vue'

  const type = defineModel<AutomationActionType | null>('type', { required: true })

  const options = computed<SelectOption[]>(() => {
    const allOptions = automationActionTypes.map(type => {
      const label = automationActionTypeLabels[type]

      return {
        label,
        value: type,
      }
    })

    if (type.value === 'do-nothing') {
      return allOptions
    }

    return allOptions.filter(option => option.value !== 'do-nothing')
  })
</script>