<template>
  <m-simple-select v-model="selectedColorMode" :options="colorModes" class="color-scheme-select">
    <template #selected-option-label="{ label }">
      <ColorSchemeSelectOption :color-mode="label" show-icon />
    </template>
    <template #option-label="{ label }">
      <ColorSchemeSelectOption :color-mode="label" />
    </template>
  </m-simple-select>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import ColorSchemeSelectOption from '@/components/ColorSchemeSelectOption.vue'
  import { colorModes, ColorMode, colorMode, setColorMode } from '@/services/ColorMode'

  const selectedColorMode = computed({
    get() {
      return colorMode.value
    },
    set(value: ColorMode) {
      setColorMode(value)
    },
  })
</script>