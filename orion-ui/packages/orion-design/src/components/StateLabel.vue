<template>
  <span class="state-label correct-text" :class="backgroundClass">
    {{ name }}
  </span>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'

  const props = defineProps<{ name: string, type: string }>()

  const backgroundClass = computed(() => {
    return `${props.type.toLowerCase()}-bg`
  })
</script>

<style lang="scss">
.state-label {
  display: inline-block;
  font-family: barlow;
  font-size: 13px;
  font-weight: 600;
  height: 20px;
  border-radius: 4px;
  padding: 0 8px;
  text-transform: capitalize;
  align-self: center;
  letter-spacing: -0.09px;
  line-height: 18px;
}
</style>
