<script>
export default {
  props: {
    type: {
      required: true,
      type: String,
      validator: label => {
        return typeof label == 'string'
      }
    }
  },
  computed: {
    resultIcon() {
      switch (this.type) {
        case 'flow':
          return 'timeline'
        case 'flow_run':
          return 'trending_up'
        case 'task':
          return 'fiber_manual_record'
        case 'task_run':
          return 'done_all'
        default:
          return ''
      }
    }
  }
}
</script>

<template>
  <v-list-item-avatar>
    <v-icon>{{ resultIcon }}</v-icon>
  </v-list-item-avatar>
</template>
