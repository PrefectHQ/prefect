<template>
  <div class="queue">
    Queue {{ id }}
  </div>
</template>

<script lang="ts" setup>
  import { useRouteParam } from '@prefecthq/orion-design'

  const id = useRouteParam('id')
</script>

<style>
.queue {}
</style>