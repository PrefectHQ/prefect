<template>
  <p-card>
    <NotificationForm v-model:notification="createNotification" @submit="submit" />
  </p-card>
</template>

<script lang="ts" setup>
  import { NotificationForm } from '@prefecthq/orion-design'
  import { ref } from 'vue'

  const createNotification = ref<Partial<Notification>>({})
  function submit(notification: Partial<Notification>): void {
    console.log({ notification })
  }
</script>