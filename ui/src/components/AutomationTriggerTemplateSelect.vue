<template>
  <p-select v-model="internalModelValue" empty-message="Select template" :options="options" class="automation-trigger-template-select" />
</template>

<script lang="ts" setup>
  import { SelectOptionNormalized } from '@prefecthq/prefect-design'
  import { AutomationTriggerTemplate, automationTriggerTemplates, getAutomationTriggerTemplateLabel } from '@prefecthq/prefect-ui-library'
  import { computed } from 'vue'

  const props = defineProps<{
    modelValue: AutomationTriggerTemplate | null,
  }>()

  const emit = defineEmits<{
    (event: 'update:modelValue', value: AutomationTriggerTemplate | null): void,
  }>()

  /**
   * Currently OSS doesn't have support for enabled/disabled trigger types like cloud does.
   * Only because it wasn't needed at the time of porting automations to OSS.
   */
  const options = computed<SelectOptionNormalized[]>(() => automationTriggerTemplates.map(type => {
    return {
      label: getAutomationTriggerTemplateLabel(type),
      value: type,
    }
  }))

  const internalModelValue = computed({
    get() {
      return props.modelValue
    },
    set(value) {
      emit('update:modelValue', value)
    },
  })
</script>