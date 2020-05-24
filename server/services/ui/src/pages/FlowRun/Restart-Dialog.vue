<script>
export default {
  props: {
    flowRun: {
      required: true,
      type: Object
    }
  },
  data() {
    return {
      error: false
    }
  },
  computed: {
    hasResultHandler() {
      return !!this.flowRun.flow.result_handler
    }
  },
  methods: {
    cancel() {
      this.$emit('cancel')
    },
    async restart() {
      this.cancel()
      try {
        const logSuccess = await this.writeLogs()
        if (logSuccess) {
          let taskStates
          if (this.utilityDownstreamTasks) {
            taskStates = this.utilityDownstreamTasks.map(task => {
              return {
                version: task.task.task_runs[0].version,
                task_run_id: task.task.task_runs[0].id,
                state: { type: 'Pending', message: this.message }
              }
            })
          } else {
            taskStates = {
              version: this.failedTaskRuns.version,
              task_run_id: this.failedTaskRuns.id,
              state: { type: 'Pending', message: this.message }
            }
          }
          if (taskStates) {
            const result = await this.$apollo.mutate({
              mutation: require('@/graphql/TaskRun/set-task-run-states.gql'),
              variables: {
                setTaskRunStatesInput: taskStates
              }
            })
            if (result?.data?.set_task_run_states) {
              const { data } = await this.$apollo.mutate({
                mutation: require('@/graphql/TaskRun/set-flow-run-states.gql'),
                variables: {
                  flowRunId: this.flowRun.id,
                  version: this.flowRun.version,
                  state: { type: 'Scheduled', message: this.message }
                }
              })

              if (data?.set_flow_run_states) {
                this.$toasted.show('Flow has been set for restart', {
                  containerClass: 'toast-typography',
                  type: 'success',
                  action: {
                    text: 'Close',
                    onClick(e, toastObject) {
                      toastObject.goAway(0)
                    }
                  },
                  duration: 5000
                })
              } else {
                this.error = true
              }
            } else {
              this.error = true
            }
          }
        } else {
          this.error = true
        }
      } catch (error) {
        this.error = true
        throw error
      }
      if (this.error === true) {
        this.$toasted.show('We hit a problem.  Please try restarting again.', {
          containerClass: 'toast-typography',
          type: 'error',
          action: {
            text: 'Close',
            onClick(e, toastObject) {
              toastObject.goAway(0)
            }
          },
          duration: 5000
        })
      }
    },
    async writeLogs() {
      const { data } = await this.$apollo.mutate({
        mutation: require('@/graphql/Update/writelogs.gql'),
        variables: {
          flowRunId: this.flowRun.id,
          name: this.name,
          message: this.message
        }
      })
      return data?.write_run_logs?.success
    }
  },
  apollo: {
    failedTaskRuns: {
      query: require('@/graphql/FlowRun/failed-task-runs.gql'),
      variables() {
        return {
          flowRunId: this.flowRun.id
        }
      },
      pollInterval: 1000,
      update: data => {
        if (data.task_run) {
          if (data.task_run.length > 1) {
            let taskRunString = ''
            data.task_run.forEach(taskRun => {
              taskRunString += taskRun.task_id + ','
            })
            const failedTaskRunString = taskRunString.slice(0, -1)
            return failedTaskRunString
          } else {
            return data.task_run[0]
          }
        }
      }
    },
    utilityDownstreamTasks: {
      query: require('@/graphql/TaskRun/utility_downstream_tasks.gql'),
      variables() {
        return {
          taskIds: `{${this.failedTaskRuns}}`,
          flowRunId: this.flowRun.id
        }
      },
      pollInterval: 1000,
      skip() {
        const hasFailedTRs = typeof this.failedTaskRuns === 'string'
        return !hasFailedTRs
      },
      update: data => data.utility_downstream_tasks
    }
  }
}
</script>

<template>
  <v-card tile>
    <v-card-title>
      Restart from failed?
    </v-card-title>

    <v-card-text v-if="hasResultHandler">
      Click on confirm to restart
      <span class="font-weight-bold">{{ flowRun.name }}</span> from its failed
      task run(s).
    </v-card-text>
    <v-card-text v-else>
      <span class="font-weight-bold black--text">
        Warning: If this flow run does not have a result handler, restarting is
        unlikely to succeed.
      </span>

      To learn more about result handlers, check out
      <router-link
        to="docs"
        target="_blank"
        href="https://docs.prefect.io/core/concepts/results.html#results-and-result-handlers"
      >
        Results and Result Handlers
      </router-link>
      in the Prefect Core docs.

      <div class="pt-5">
        Click on confirm to restart
        <span class="font-weight-bold">{{ flowRun.name }}</span> anyway.
      </div>
    </v-card-text>
    <v-card-actions>
      <v-spacer></v-spacer>

      <v-tooltip bottom>
        <template v-slot:activator="{ on }">
          <div v-on="on">
            <v-btn
              :disabled="!failedTaskRuns"
              color="primary"
              @click="restart"
              v-on="on"
            >
              Confirm
            </v-btn>
          </div>
        </template>
        <span v-if="!failedTaskRuns">
          You can only restart a flow run with failed tasks.
        </span>
      </v-tooltip>

      <v-btn text @click="cancel">
        Cancel
      </v-btn>
    </v-card-actions>
  </v-card>
</template>
