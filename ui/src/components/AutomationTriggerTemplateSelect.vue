<template>
  <p-select v-model="template" empty-message="Select template" :options="options" class="automation-trigger-template-select" />
</template>

<script lang="ts" setup>
  import { SelectOptionNormalized } from '@prefecthq/prefect-design'
  import { AutomationTriggerTemplate, automationTriggerTemplates, getAutomationTriggerTemplateLabel } from '@prefecthq/prefect-ui-library'
  import { computed } from 'vue'

  const template = defineModel<AutomationTriggerTemplate | null>('template', { required: true })

  /*
   * Currently OSS doesn't have support for enabled/disabled trigger templates like cloud does.
   * Only because it wasn't needed at the time of porting automations to OSS.
   */
  const options = computed<SelectOptionNormalized[]>(() => automationTriggerTemplates.map(type => {
    return {
      label: getAutomationTriggerTemplateLabel(type),
      value: type,
    }
  }))
</script>