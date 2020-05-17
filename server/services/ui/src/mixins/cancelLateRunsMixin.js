import gql from 'graphql-tag'

export const cancelLateRunsMixin = {
  data() {
    return {
      // Clearing late runs
      clearLateRunsError: false,
      isClearingLateRuns: false,
      showClearLateRunsDialog: false
    }
  },
  watch: {
    lateRuns() {
      if (this.lateRuns.length === 0 && this.isClearingLateRuns) {
        this.isClearingLateRuns = false
      }
    }
  },
  methods: {
    async clearLateRuns() {
      try {
        this.showClearLateRunsDialog = false
        this.isClearingLateRuns = true
        const statesMutation = this.lateRuns.map(
          (flowRun, fi) => `
            setFlowRunStates${fi}: set_flow_run_states(
              input: {
                states: [{
                  flow_run_id: "${flowRun.id}",
                  state: {
                    type: "Cancelled"
                  },
                  version: ${flowRun.version}
                }]
              }
            ) {
              states {
                id
                status
              }
            }
            setTaskRunStates${fi}: set_task_run_states(
              input: {
                states: [${flowRun.task_runs
                  .map(
                    taskRun => `{
                    version: ${taskRun.version},
                    task_run_id: "${taskRun.id}",
                    state: {
                      type: "Cancelled"
                    }}`
                  )
                  .join(', ')}
                  ]}) {
                    states {
                      id
                    }
                  }
              `
        )
        // Build mutation to delete late flow runs.
        const mutation = gql`
          mutation {
            ${statesMutation}
          }
        `

        // Cancel flow runs & task runs
        await this.$apollo.mutate({ mutation })

        // Refetch upcoming flows
        await this.$apollo.queries.upcoming.refetch()
      } catch (error) {
        this.clearLateRunsError = true
        throw error
      }
    }
  }
}
