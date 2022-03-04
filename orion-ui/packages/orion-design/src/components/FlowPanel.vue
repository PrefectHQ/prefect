<template>
  <m-panel>
    <template #title>
      hello world
    </template>
  </m-panel>
</template>

<script lang="ts" setup>
  import { Flow } from '@/models/Flow'

  defineProps<{
    flow: Flow,
  }>()
</script>

<style lang="scss" scoped>

</style>