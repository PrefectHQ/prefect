<script>
import moment from 'moment-timezone'

export default {
  props: {
    startTime: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      duration: null,
      interval: null
    }
  },
  mounted() {
    this.interval = setInterval(() => {
      let now = new moment(),
        start = new moment(this.startTime)
      this.duration = moment.duration(now.diff(start))
    }, 1000)
  },
  beforeDestroy() {
    clearInterval(this.interval)
  }
}
</script>

<template>
  <span>{{ duration | duration }}</span>
</template>
