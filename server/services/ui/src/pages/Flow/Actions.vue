<script>
import DeleteButton from '@/components/DeleteFlowButton'

export default {
  components: {
    DeleteButton
  },
  props: {
    flow: {
      required: true,
      type: Object
    },
    archived: {
      required: true,
      type: Boolean
    },
    scheduled: {
      required: true,
      type: Boolean
    }
  },
  data() {
    return {
      scheduleLoading: false
    }
  },
  computed: {
    schedule() {
      return this.flow.schedules.length ? this.flow.schedules[0] : null
    },
    isQuickRunnable() {
      if (!this.flow.parameters) return true

      return this.flow.parameters.reduce((result, param) => {
        if (param.required) return false
        return result
      }, true)
    },
    isScheduled: {
      get() {
        if (this.archived) return false
        return this.schedule ? !!this.schedule.active : false
      },
      set() {
        return
      }
    }
  },
  methods: {
    archiveFlow() {},
    deleteFlow() {},
    goToRunFlowPage() {
      this.$router.push({
        name: 'flow',
        params: { id: this.flow.id },
        query: { run: '' }
      })
    },
    async quickRunFlow() {
      try {
        const flowRunResponse = await this.$apollo.mutate({
          mutation: require('@/graphql/Mutations/create-flow-run.gql'),
          variables: {
            flowId: this.flow.id
          }
        })

        this.$router.push({
          name: 'flow-run',
          params: { id: flowRunResponse?.data?.create_flow_run?.id }
        })

        this.quickRunSuccessAlert()
      } catch (err) {
        this.quickRunErrorAlert()
        throw new Error(err)
      }
    },
    quickRunErrorAlert() {
      this.$toasted.error(
        'Something went wrong while trying to quick-run your flow. Please try again.',
        {
          containerClass: 'toast-typography',
          icon: 'error',
          action: {
            text: 'Close',
            onClick(e, toastObject) {
              toastObject.goAway(0)
            }
          },
          duration: 5000
        }
      )
    },
    quickRunSuccessAlert() {
      this.$toasted.success('Your flow run has been successfully scheduled.', {
        containerClass: 'toast-typography',
        icon: 'check_circle',
        action: {
          text: 'Close',
          onClick(e, toastObject) {
            toastObject.goAway(0)
          }
        },
        duration: 3000
      })
    },
    async scheduleFlow() {
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
        this.scheduleLoading = true
        let response

        if (this.isScheduled) {
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
        } else if (!this.isScheduled) {
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
        this.$toasted.error(errorMessage, toastConfig)
        throw error
      } finally {
        this.scheduleLoading = false
      }
    },
    unarchiveFlow() {}
  }
}
</script>

<template>
  <div
    class="pa-0 mb-2 d-flex align-center"
    :class="$vuetify.breakpoint.smAndDown ? 'justify-center' : 'justify-end'"
  >
    <v-tooltip
      bottom
      max-width="340"
      :open-delay="!isQuickRunnable || archived ? 0 : 750"
    >
      <template v-slot:activator="{ on }">
        <div v-on="on">
          <v-btn
            class="vertical-button mr-2 py-1 position-relative"
            color="primary"
            text
            tile
            small
            data-cy="start-flow-quick-run"
            :disabled="!isQuickRunnable || archived"
            @click="quickRunFlow"
          >
            <v-icon>fa-rocket</v-icon>
            <v-icon
              small
              class="position-absolute"
              :style="{
                bottom: '-4px',
                right: '8px',
                transform: 'rotate(15deg)'
              }"
              >offline_bolt</v-icon
            >
            <div class="mb-1">Quick Run</div>
          </v-btn>
        </div>
      </template>
      <span v-if="!isQuickRunnable">
        This flow has required parameters that must be set before a run. Select
        the RUN tab to launch this flow.
      </span>
      <span v-else-if="archived">
        This flow is archived and cannot be run.
      </span>
      <span v-else>
        <p>
          Run this flow immediately, with a generated flow run name and default
          parameters.
        </p>

        <p class="mb-0">
          Select the RUN tab if you want to customize the flow run name, set
          specific parameters, or provide context.
        </p>
      </span>
    </v-tooltip>

    <div class="vertical-divider"></div>

    <v-tooltip bottom>
      <template v-slot:activator="{ on }">
        <div v-on="on">
          <div class="vertical-button">
            <v-switch
              v-model="isScheduled"
              hide-details
              class="v-input--vertical"
              color="primary"
              :loading="scheduleLoading"
              :disabled="schedule == null || archived"
              @change="scheduleFlow"
            >
              <template v-slot:label>
                <v-btn tile small text disabled class="mb-1">Schedule</v-btn>
              </template>
            </v-switch>
          </div>
        </div>
      </template>
      <span v-if="schedule == null">
        This flow does not have a schedule.
      </span>
      <span v-else-if="archived">
        Archived flows cannot be scheduled.
      </span>
      <span v-else>
        Turn {{ isScheduled ? 'off' : 'on' }} this flow's schedule
      </span>
    </v-tooltip>

    <DeleteButton :flow="flow" type="flow" />
  </div>
</template>

<style lang="scss">
.vertical-divider {
  border-left: 0.5px solid rgba(0, 0, 0, 0.26);
  border-right: 0.5px solid rgba(0, 0, 0, 0.26);
  height: 75%;
}

// stylelint-disable
.vertical-button {
  &.v-btn--tile {
    height: auto !important;
  }

  .v-btn__content {
    flex-direction: column-reverse !important;
  }
}
//stylelint-enable

// stylelint-disable
.v-input--vertical {
  margin-top: 0 !important;
  padding-top: 0 !important;

  .v-input__slot {
    flex-direction: column-reverse !important;

    .v-input--selection-controls__input {
      align-self: center;
      margin: auto !important;
      transform: scale(0.9);
    }
  }

  .v-btn:not(.v-btn--round).v-size--small {
    height: unset !important;
  }
}
// stylelint-enable
</style>
