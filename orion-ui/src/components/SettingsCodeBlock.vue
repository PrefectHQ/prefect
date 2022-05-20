<template>
  <div v-if="settingSections" class="settings-block">
    <PCode multiline>
      <div v-for="section, index in settingSections" :key="index">
        {{ section[0] }}: {{ section[1] }}
      </div>
    </PCode>
  </div>
</template>

<script lang="ts" setup>
  import { Settings } from '@prefecthq/orion-design'
  import { PCode } from '@prefecthq/prefect-design'
  import { defineProps, computed } from 'vue'

  const props = defineProps<{
    engineSettings: Settings,
  }>()

  const settingSections = Object.entries(props.engineSettings)
</script>

<style>
.settings-block { @apply
  overscroll-contain
  m-4
}
</style>