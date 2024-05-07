<template>
  <p-virtual-scroller :items="automations" class="automations-list">
    <template #default="{ item: automation }">
      <AutomationCard :automation="automation" @update="emit('update')" />
    </template>
  </p-virtual-scroller>
</template>

<script lang="ts" setup>
  import AutomationCard from '@/components/AutomationCard.vue'
  import { CloudAutomation } from '@/models/automation'

  defineProps<{
    automations: CloudAutomation[],
  }>()

  const emit = defineEmits<{
    (event: 'delete' | 'update'): void,
  }>()
</script>

<style>
.automations-list {
  --virtual-scroller-item-gap: theme('spacing.2')
}
</style>