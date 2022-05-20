<template>
  <PCode>
    {{ engineSettings }}
  </PCode>
</template>

<script lang="ts" setup>
  import { Settings } from '@prefecthq/orion-design'
  import { PCode } from '@prefecthq/prefect-design'
  import { defineProps, computed } from 'vue'

  const props = defineProps<{
    engineSettings: Settings,
  }>()
</script>

<style>
.settings {}
</style>