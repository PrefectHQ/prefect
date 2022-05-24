<template>
  <div class="settings-block">
    <PCode multiline>
      <div v-for="(section, index) in settingSections" :key="index">
        {{ section[0] }}: {{ section[1] }}
      </div>
    </PCode>
  </div>
</template>

<script lang="ts" setup>
  import { OrionSettings } from '@prefecthq/orion-design'
  import { PCode } from '@prefecthq/prefect-design'
  import { defineProps, computed } from 'vue'

  const props = defineProps<{
    engineSettings: OrionSettings,
  }>()

  const settingSections = computed(() => Object.entries(props.engineSettings))
</script>

<style>
.settings-block {}
</style>
