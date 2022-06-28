<template>
  <p-layout-default class="flows">
    <template #header>
      <PageHeadingNotifications />
    </template>
    <template v-if="loaded">
      <template v-if="empty">
        <NotificationsPageEmptyState />
      </template>

      <template v-else>
        <NotificationsTable :notifications="notifications" @delete="notificationsSubscription.refresh()" @update="notificationsSubscription.refresh()" />
      </template>
    </template>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Notification, NotificationsTable, NotificationsPageEmptyState, PageHeadingNotifications, NotificationFilter } from '@prefecthq/orion-design'
  import { useSubscription } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { notificationsApi } from '@/services/notificationsApi'

  const subscriptionOptions = {
    interval: 30000,
  }

  const filter: NotificationFilter = {}

  const notificationsSubscription = useSubscription(notificationsApi.getNotifications, [filter], subscriptionOptions)
  const notifications = computed<Notification[]>(() => notificationsSubscription.response ?? [])
  const empty = computed(() => notificationsSubscription.executed && notifications.value.length === 0)
  const loaded = computed(() => notificationsSubscription.executed)
</script>
