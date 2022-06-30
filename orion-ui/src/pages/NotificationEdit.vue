<template>
  <p-card>
    <NotificationForm v-if="notification" v-model:notification="notification" @submit="submit" />
  </p-card>
</template>

<script lang="ts" setup>
  import { NotificationForm, Notification, INotificationUpdateRequest } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import router, { routes } from '@/router'
  import { notificationsApi } from '@/services/notificationsApi'

  const notificationId = useRouteParam('notificationId')
  const notification = ref({ ...await notificationsApi.getNotification(notificationId.value) })

  function mapNotificationUpdateToNotificationUpdateRequest(notificationUpdate: Partial<Notification>): INotificationUpdateRequest {
    return {
      name: notificationUpdate.name,
      state_names: notificationUpdate.stateNames,
      tags: notificationUpdate.tags,
      is_active: notificationUpdate.isActive,
    }
  }

  async function submit(notificationSource: Partial<Notification>): Promise<void> {
    try {
      const notificationUpdate: INotificationUpdateRequest = mapNotificationUpdateToNotificationUpdateRequest(notificationSource)
      await notificationsApi.updateNotification(notificationId.value, notificationUpdate)
      router.push(routes.notifications())
    } catch (error) {
      showToast('Error updating notification', 'error')
      console.warn(error)
    }
  }
</script>