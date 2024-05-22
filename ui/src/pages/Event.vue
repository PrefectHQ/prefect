<template>
  <p-layout-default v-if="event" class="event">
    <template #header>
      <PageHeading :crumbs="crumbs">
        <template #actions>
          <WorkspaceEventMenu :event="event" />
        </template>
      </PageHeading>
    </template>

    <WorkspaceEventDetails :event />
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Crumb } from '@prefecthq/prefect-design'
  import { PageHeading, parseRouteDate, WorkspaceEventMenu, WorkspaceEventDetails, useWorkspaceApi, useWorkspaceRoutes, useTimeScopedWorkspaceEventsFilter } from '@prefecthq/prefect-ui-library'
  import { useRouteParam } from '@prefecthq/vue-compositions'
  import { computed } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'

  const api = useWorkspaceApi()
  const routes = useWorkspaceRoutes()
  const date = useRouteParam('eventDate')
  const eventId = useRouteParam('eventId')
  const eventDate = computed(() => parseRouteDate(date.value))
  const filter = useTimeScopedWorkspaceEventsFilter({ startDate: eventDate, eventId: [eventId.value] })
  const event = await api.events.getFirstEvent(filter.value)

  const crumbs = computed<Crumb[]>(() => [
    { text: 'Event Feed', to: routes.events() },
    { text: event.eventLabel },
  ])

  usePageTitle(`Event: ${event.eventLabel}`)
</script>