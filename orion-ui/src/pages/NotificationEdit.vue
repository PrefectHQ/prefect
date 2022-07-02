<template>
  <p-card>
    <NotificationForm v-if="notification" v-model:notification="notification" @submit="submit" @cancel="cancel" />
  </p-card>
</template>

<script lang="ts" setup>
  import { NotificationForm, Notification, INotificationUpdateRequest, titleCase } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import router, { routes } from '@/router'
  import { notificationsApi } from '@/services/notificationsApi'

  const notificationId = useRouteParam('notificationId')
  const notification = ref({ ...await notificationsApi.getNotification(notificationId.value) })

  function mapNotificationUpdateToNotificationUpdateRequest(notificationUpdate: Partial<Notification>): INotificationUpdateRequest {
    const stateNames = notification.value.stateNames.map(name=> titleCase(name))
    return {
      state_names: stateNames,
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

  function cancel(): void {
    router.push(routes.notifications())
  }
</script>