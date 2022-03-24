<template>
  <div class="color-scheme-select-option">
    <div class="color-scheme-select-option__label">
      <i v-if="showIcon" class="color-scheme-select-option__icon pi pi-palette-line" />
      <div class="color-scheme-select-option__color-name">
        {{ colorMode }}
      </div>
    </div>
    <div class="color-scheme-select-option__colors">
      <div
        v-for="color in colors"
        :key="color"
        class="color-scheme-select-option__color"
        :style="{ 'background-color': color }"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { stateType } from '@/models/StateType'
  import { ColorMode } from '@/services/ColorMode'
  const props = defineProps<{
    showIcon?: boolean,
    colorMode: ColorMode,
  }>()
  const computedStyle = window.getComputedStyle(document.documentElement)
  const colors = computed(() => {
    return stateType.map((state) => {
      const ref = `--${state}-${props.colorMode}`.toLowerCase()
      return computedStyle.getPropertyValue(ref)
    })
  })
</script>

<style lang="scss">
.color-scheme-select-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.color-scheme-select-option__label {
  display: flex;
  align-items: center;
  gap: 4px;
}
.color-scheme-select-option__color-name {
  text-transform: capitalize;
}
.color-scheme-select-option__colors {
  display: flex;
  gap: 2px;
}
.color-scheme-select-option__color {
  border-radius: 50%;
  border: 1px solid #eee;
  height: 15px;
  width: 15px;
}
</style>