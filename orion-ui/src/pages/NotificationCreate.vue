<template>
  <p-layout-default>
    <template #header>
      <PageHeadingNotificationCreate />
    </template>
    <NotificationForm v-model:notification="notificationCreate" @submit="submit" @cancel="cancel" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { NotificationForm, Notification, PageHeadingNotificationCreate } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { ref } from 'vue'
  import router, { routes } from '@/router'
  import { notificationsApi } from '@/services/notificationsApi'

  const notificationCreate = ref({})
  async function submit(notification: Partial<Notification>): Promise<void> {
    try {
      await notificationsApi.createNotification(notification)
      router.push(routes.notifications())
    } catch (error) {
      showToast('Error creating notification', 'error')
      console.warn(error)
    }
  }

  function cancel(): void {
    router.push(routes.notifications())
  }
</script>