<template>
  <p-card>
    <NotificationForm v-if="notification" v-model:notification="notification" @submit="submit" />
  </p-card>
</template>

<script lang="ts" setup>
  import { NotificationForm } from '@prefecthq/orion-design'
  import { useSubscription, useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { notificationsApi } from '@/services/notificationsApi'

  const notificationId = useRouteParam('notificationId')
  const notificationSubscription = useSubscription(notificationsApi.getNotification, [notificationId.value])
  const notification = computed(() => notificationSubscription.response)
  function submit(notification: Partial<Notification>): void {
    console.log({ notification })
  }
</script>