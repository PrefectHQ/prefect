<template>
  <span>
    Connection error - Check connection settings or go to the <p-link class="connection-toast-message__link" to="https://docs.prefect.io/concepts/settings/">settings docs</p-link>for help
  </span>
</template>

<script lang="ts" setup>
  import { PLink } from '@prefecthq/prefect-design'
</script>

<style>
  .connection-toast-message__link {
    @apply text-blue-400 !important
  }
</style>