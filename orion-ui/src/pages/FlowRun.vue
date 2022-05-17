<template>
  <div class="flow-run">
    Flow run {{ id }}
  </div>
</template>

<script lang="ts" setup>
  import { useRouteParam } from '@prefecthq/orion-design'

  const id = useRouteParam('id')
</script>

<style>
.flow-run {}
</style>