<template>
  <div class="settings-block">
    <p-code multiline>
      <div v-for="(section, index) in settingSections" :key="index" class="settings-block--code-line">
        {{ section[0] }}: {{ section[1] }}
      </div>
    </p-code>
  </div>
</template>

<script lang="ts" setup>
  import { OrionSettings } from '@prefecthq/orion-design'
  import { PCode } from '@prefecthq/prefect-design'
  import { computed } from 'vue'

  const props = defineProps<{
    engineSettings: OrionSettings,
  }>()
  const settingSections = computed(() => Object.entries(props.engineSettings))
</script>

<style>
.settings-block--code-line {
  @apply whitespace-pre-wrap;
}
</style>
