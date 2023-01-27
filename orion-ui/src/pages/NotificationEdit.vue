<template>
  <p-layout-default>
    <template #header>
      <PageHeadingNotificationEdit />
    </template>
    <NotificationForm v-if="notification" v-model:notification="notification" @submit="submit" @cancel="cancel" />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { NotificationForm, Notification, PageHeadingNotificationEdit, useWorkspaceApi } from '@prefecthq/orion-design'
  import { showToast } from '@prefecthq/prefect-design'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { ref } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import router, { routes } from '@/router'

  const api = useWorkspaceApi()
  const notificationId = useRouteParam('notificationId')
  const notification = ref({ ...await api.notifications.getNotification(notificationId.value) })

  async function submit(notification: Partial<Notification>): Promise<void> {
    try {
      await api.notifications.updateNotification(notificationId.value, notification)
      router.push(routes.notifications())
    } catch (error) {
      showToast('Error updating notification', 'error')
      console.warn(error)
    }
  }

  function cancel(): void {
    router.push(routes.notifications())
  }

  usePageTitle('Edit Notification')
</script>