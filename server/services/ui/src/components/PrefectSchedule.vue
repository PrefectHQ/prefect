<script>
import { intervalToEnglish } from '@/utils/dateTime'
import cronstrue from 'cronstrue'

// TODO add button that opens a sidebar to show multiple schedules (#307)

export default {
  props: {
    schedule: {
      required: true,
      type: Object,
      validator: schedule => schedule.type
    }
  },
  computed: {
    displaySchedule() {
      if (this.schedule.type === 'CronSchedule') {
        // If there's a start date and a timezone, add a space and show it
        const timeZone =
          this.schedule.start_date && this.schedule.start_date.tz
            ? ` ${this.schedule.start_date.tz}`
            : ''
        return `${cronstrue.toString(this.schedule.cron)}${timeZone}`
      } else if (this.schedule.type === 'IntervalSchedule') {
        const microsecondsString = this.schedule.interval
        const numberOfMilliseconds = Number(microsecondsString) * 0.001

        return intervalToEnglish(numberOfMilliseconds)
      }
      return null
    }
  }
}
</script>

<template>
  <span
    v-if="
      schedule.type === 'CronSchedule' || schedule.type === 'IntervalSchedule'
    "
  >
    {{ displaySchedule }}
  </span>
  <span v-else>
    <v-btn disabled small>{{
      schedule.type === 'UnionSchedule' ? 'union schedule' : 'custom schedule'
    }}</v-btn>
  </span>
</template>
