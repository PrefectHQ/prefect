<template>
  <div class="flow">
    Flow {{ id }}
  </div>
</template>

<script lang="ts" setup>
  import { useRouteParam } from '@prefecthq/orion-design'

  const id = useRouteParam('id')
</script>

<style>
.flow {}
</style>