<template>
  <p-layout-default v-if="startDate && endDate" class="events">
    <template #header>
      <PageHeading :crumbs="crumbs" />
    </template>

    <div class="events__content">
      <div class="events__filters">
        <p-label label="Resource">
          <template #default="{ id }">
            <EventResourceCombobox :id v-model:selected="resources" multiple />
          </template>
        </p-label>

        <p-label label="Events">
          <template #default="{ id }">
            <EventsCombobox :id v-model:selected="eventsQueryParam" multiple />
          </template>
        </p-label>
      </div>

      <div ref="chart" class="events__chart p-background" :class="classes.chart">
        <WorkspaceEventsLineChart v-model:start-date="startDate" v-model:end-date="endDate" :filter :zoom-options />
        <div class="events__controls">
          <DateRangeSelect v-model="dateRange.range" :max="now" />
        </div>
      </div>

      <template v-if="loading && empty">
        <p-empty-results>
          <template #message>
            Loading events
          </template>
        </p-empty-results>
      </template>

      <template v-else>
        <template v-if="empty">
          <p-empty-results>
            <template #message>
              No events
            </template>
          </p-empty-results>
        </template>

        <WorkspaceEventsTimeline class="events__timeline" :events :start-date :end-date />

        <p-pager
          v-if="events.length"
          v-model:page="page"
          v-model:pages="pages"
          class="events__pager"
        />
      </template>
    </div>
  </p-layout-default>
</template>

<script lang="ts" setup>
  import { Crumb, useOffsetStickyRootMargin } from '@prefecthq/prefect-design'
  import {
    Getter,
    PageHeading,
    separate,
    DateRangeSelect,
    useDateRangeSelectValueFromRoute,
    secondsInDay,
    useWorkspaceEventsSubscription,
    EventsCombobox,
    EventResourceCombobox,
    WorkspaceEventsFilter,
    WorkspaceEventsTimeline,
    WorkspaceEventsLineChart,
    secondsInHour,
    secondsInWeek
  } from '@prefecthq/prefect-ui-library'
  import { ChartZoomOptions, useChartSelection, useChartZoom } from '@prefecthq/vue-charts'
  import { UsePositionStickyObserverOptions, useNow, usePositionStickyObserver, useRouteQueryParam } from '@prefecthq/vue-compositions'
  import debounce from 'lodash.debounce'
  import { computed, ref, toRef, watch } from 'vue'
  import { usePageTitle } from '@/compositions/usePageTitle'
  import { mapper } from '@/services/mapper'

  const crumbs = computed<Crumb[]>(() => [{ text: 'Event Feed' }])
  const chart = ref()
  const interval = 60_000
  const { now } = useNow({ interval })

  usePageTitle('Event Feed')

  const resources = useRouteQueryParam('resource', [])
  const eventsQueryParam = useRouteQueryParam('events', [])

  const dateRange = useDateRangeSelectValueFromRoute({
    type: 'span',
    seconds: -secondsInDay,
  })

  const { startDate, endDate } = useChartZoom()
  const { selectionStart, selectionEnd } = useChartSelection()

  // minus one second from each to get clean dates like 10:00AM - 10:59AM
  const zoomOptions: ChartZoomOptions = {
    minRangeInSeconds: secondsInHour - 1,
    maxRangeInSeconds: secondsInWeek - 1,
  }

  const filter = toRef(() => {
    const { startDate, endDate } = mapper.map('DateRangeSelectValue', dateRange.range, 'DateRange')!
    const [prefixed, name] = separate(eventsQueryParam.value, event => event.endsWith('*'))
    const prefix = prefixed.map(prefix => prefix.replace('.*', '.'))

    // Exclude some events by default unless they are explicitly requested
    const excludedByDefault = ['prefect.log.write']
    const excludeName = excludedByDefault.filter(excluded => !name.includes(excluded))

    const filter: WorkspaceEventsFilter = {
      occurred: {
        since: selectionStart.value ?? startDate,
        until: selectionEnd.value ?? endDate,
      },
      anyResource: {
        idPrefix: resources.value,
      },
      event: {
        prefix,
        name,
        excludeName,
      },
    }

    return filter
  })

  const { page, pages, loading, events, empty } = useWorkspaceEventsSubscription(filter, { interval })

  const { margin } = useOffsetStickyRootMargin()
  const stickyObserverOptions: Getter<UsePositionStickyObserverOptions> = () => ({
    rootMargin: margin.value,
  })
  const { stuck } = usePositionStickyObserver(chart, stickyObserverOptions)
  const classes = computed(() => ({
    chart: {
      'events__chart--stuck': stuck.value,
    },
  }))

  let updatedDateRange = false

  const updateDateRangeSelectValue = debounce(() => {
    if (!startDate.value || !endDate.value) {
      return
    }

    if (updatedDateRange) {
      updatedDateRange = false
      return
    }

    dateRange.range = {
      type: 'range',
      startDate: startDate.value,
      endDate: endDate.value,
    }
  }, 1000)

  watch([startDate, endDate], () => updateDateRangeSelectValue())

  function updateDateRangeValue(): void {
    if (!dateRange.range) {
      return
    }

    const { startDate: newStart, endDate: newEnd } = mapper.map('DateRangeSelectValue', dateRange.range, 'DateRange')

    if (startDate.value?.getTime() !== newStart.getTime()) {
      updatedDateRange = true
      startDate.value = newStart
    }

    if (endDate.value?.getTime() !== newEnd.getTime()) {
      updatedDateRange = true
      endDate.value = newEnd
    }
  }

  watch(() => dateRange.range, () => updateDateRangeValue())

  updateDateRangeValue()
</script>

<style>
.events__content { @apply
  grid
  gap-1
  grid-cols-1
}

.events__filters { @apply
  flex
  flex-col
  gap-4
  sm:flex-row
  mb-7
}

.events__chart { @apply
  sticky
  top-0
  z-10
  pb-3
  grid
  grid-cols-1
  gap-3
  rounded-t-default
}

.events__chart--stuck { @apply
  bg-floating-sticky
  backdrop-blur-sm
  shadow-md
  rounded-t-none
  rounded-b-default
}

.events__controls { @apply
  flex
  justify-center
  p-3
}

.events__timeline { @apply
  mt-7
}

.events__pager { @apply
  mt-4
}
</style>
