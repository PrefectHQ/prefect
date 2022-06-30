<template>
  <p-card>
    <NotificationForm v-model:notification="createNotification" @submit="submit" />
  </p-card>
</template>

<script lang="ts" setup>
  import { NotificationForm, Notification, INotificationRequest } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { ref } from 'vue'
  import router, { routes } from '@/router'
  import { notificationsApi } from '@/services/notificationsApi'


  const createNotification = ref({})
  async function submit(notification: Partial<Notification>): Promise<void> {
    try {
      const notificationRequest: INotificationRequest = {
        name: 'polly',
        state_names: notification.stateNames ?? []!,
        tags: notification.tags ?? [],
        is_active: true,
        block_document_id: notification.blockDocumentId!,
      }
      await notificationsApi.createNotification(notificationRequest)
      router.push(routes.notifications())
    } catch (error) {
      showToast('Error creating notification', 'error')
      console.warn(error)
    }
  }
</script>