<template>
  <span class="run-state correct-text caption mr-1" :class="classObject">
    {{ state }}
  </span>
</template>

<script lang="ts" setup>
import { computed } from 'vue'

const props = defineProps({
  state: String,
  stateType: String
})

const classObject = computed(() => {
  if (props.stateType) {
    return `${props.stateType.toLowerCase()}-bg d-inline-block`
  }
  return `${props.state}-bg`
})
</script>

<style lang="scss" scoped>
@use '@/styles/components/label.scss';
</style>
