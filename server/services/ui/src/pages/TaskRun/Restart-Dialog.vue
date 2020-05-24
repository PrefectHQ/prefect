<script>
import { ERROR_MESSAGE } from '@/utils/error'

export default {
  props: {
    taskRun: {
      required: true,
      type: Object
    },
    flowRunId: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      error: ERROR_MESSAGE,
      tasksSuccess: null,
      name: 'PrefectCloudUIRestartButton'
    }
  },
  computed: {
    message() {
      return 'Flow run restarted'
    }
  },
  methods: {
    cancel() {
      this.$emit('cancel')
    },
    raiseWarning() {
      const hasCachedInput =
        this.taskRun.serialized_state &&
        this.taskRun.serialized_state.cached_inputs &&
        Object.keys(this.taskRun.serialized_state.cached_inputs).length
      const hasUpstreamEdges =
        this.taskRun.task &&
        this.taskRun.task.upstream_edges &&
        this.taskRun.task.upstream_edges.filter(edge => edge.key).length
      return !!hasUpstreamEdges && !hasCachedInput
    },
    async restart() {
      this.cancel()
      try {
        this.dialog = false
        const logSuccess = this.writeLogs()
        if (logSuccess) {
          let taskStates
          if (this.utilityDownstreamTasks.length) {
            taskStates = this.utilityDownstreamTasks.map(task => {
              return {
                version: task.task.task_runs[0].version,
                task_run_id: task.task.task_runs[0].id,
                state: { type: 'Pending', message: this.message }
              }
            })
          } else {
            taskStates = {
              task_run_id: this.taskRun.id,
              version: this.taskRun.version,
              state: { type: 'Pending', message: this.message }
            }
          }
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
                flowRunId: this.flowRunId,
                version: this.taskRun.flow_run.version,
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
              this.tasksSuccess = false
            }
          }
        } else {
          this.tasksSuccess = false
        }
      } catch (error) {
        this.tasksSuccess = false
        throw error
      }
      if (this.tasksSuccess === false) {
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
          flowRunId: this.flowRunId,
          name: this.name,
          message: this.message
        }
      })
      return data && data.writeRunLogs && data.writeRunLogs.success
    }
  },
  apollo: {
    taskRun: {
      query: require('@/graphql/TaskRun/task-run.gql'),
      variables() {
        return {
          id: this.taskRun.id,
          timestamp: this.heartbeat
        }
      },
      pollInterval: 1000,
      update: data => data.task_run_by_pk
    },
    utilityDownstreamTasks: {
      query: require('@/graphql/TaskRun/utility_downstream_tasks.gql'),
      variables() {
        return {
          taskIds: `{${this.taskRun.id}}`,
          flowRunId: this.flowRunId
        }
      },
      pollInterval: 1000,
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

    <v-card-text v-if="raiseWarning()">
      <div class="font-weight-bold black--text">
        Warning: This flow has upstream dependencies which have not been cached.
        If you restart the flow-run from here, it is unlikely to succeed.
      </div>
      <div class="pb-5">
        For extra information, check out
        <router-link
          to="docs"
          target="_blank"
          href="https://docs.prefect.io/core/concepts/persistence.html#input-caching"
          >Persistence and Caching</router-link
        >
        in our docs.
      </div>
      <div>
        To restart the flow run {{ taskRun.flow_run.name }} from this task run
        anyway, click on confirm.
      </div>
    </v-card-text>
    <v-card-text v-else>
      Click on confirm to restart the flow run
      {{ taskRun.flow_run.name }} from this task run.
    </v-card-text>

    <v-card-actions>
      <v-spacer></v-spacer>

      <v-tooltip bottom>
        <template v-slot:activator="{ on }">
          <div v-on="on">
            <v-btn color="primary" @click="restart" v-on="on">
              Confirm
            </v-btn>
          </div>
        </template>
      </v-tooltip>

      <v-btn text @click="cancel">
        Cancel
      </v-btn>
    </v-card-actions>
  </v-card>
</template>
