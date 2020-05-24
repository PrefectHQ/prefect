<script>
export default {
  props: {
    schedules: {
      required: true,
      type: Array
    },
    showDescription: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      loading: false
    }
  },
  computed: {
    schedule() {
      if (this.schedules.length) {
        return this.schedules[0]
      }
      return null
    }
  },
  methods: {
    async toggleScheduleActive() {
      const errorMessage =
        "Something went wrong, we're working to fix the issue. Please wait a few moments and try again."
      const toastConfig = {
        action: {
          text: 'Close',
          onClick(e, toastObject) {
            toastObject.goAway(0)
          }
        },
        duration: 5000
      }
      try {
        this.loading = true
        let response

        if (this.schedule.active) {
          response = await this.$apollo.mutate({
            mutation: require('@/graphql/Mutations/set-schedule-inactive.gql'),
            variables: {
              id: this.schedule.id
            }
          })

          if (response?.data?.set_schedule_inactive?.success) {
            this.$toasted.success('Schedule Set to Paused', toastConfig)
          } else {
            this.$toasted.error(errorMessage)
          }
        } else if (!this.schedule.active) {
          response = await this.$apollo.mutate({
            mutation: require('@/graphql/Mutations/set-schedule-active.gql'),
            variables: {
              id: this.schedule.id
            }
          })

          if (response?.data?.set_schedule_active?.success) {
            this.$toasted.success('Schedule Set to Active', toastConfig)
          } else {
            this.$toasted.error(errorMessage, toastConfig)
          }
        }
      } catch (error) {
        this.schedule.active = !this.schedule.active
        this.$toasted.error(errorMessage, toastConfig)
        throw error
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<template>
  <span v-if="loading" class="flex-span">
    <v-progress-circular indeterminate color="primary" />
  </span>

  <span v-else-if="schedule" class="flex-span">
    <v-btn class="ml-0 mr-1" text small icon @click="toggleScheduleActive">
      <v-icon v-if="schedule.active" color="accent">
        toggle_on
      </v-icon>
      <v-icon v-else-if="!schedule.active">toggle_off</v-icon>
    </v-btn>
  </span>

  <span v-else class="flex-span">
    <span v-if="showDescription">
      None
    </span>
  </span>
</template>

<style lang="scss" scoped>
.flex-span {
  align-items: center;
  display: inline-flex;
}
</style>
