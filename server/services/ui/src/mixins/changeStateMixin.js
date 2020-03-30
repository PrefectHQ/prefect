export const changeStateMixin = {
  props: {
    taskRun: {
      default: null,
      type: Object
    },
    flowRun: {
      default: null,
      type: Object
    },
    dialogType: {
      required: true,
      type: String
    }
  },
  data() {
    return {
      markAsDialog: false,
      markAsLoading: false,
      reason: '',
      e1: 1,
      formError: false,
      name: 'PrefectUIRunMarkAsButton',
      setStateError: false,
      selectedState: '',
      allTasks: false,
      cancelLoad: false,
      setStateSuccessA: false,
      setStateSuccessB: false,
      toastedMessage: 'We hit a problem.  Please try marking the state again.',
      taskStates: [
        'Finished',
        'Success',
        'Skipped',
        'Failed',
        'Looped',
        'Mapped',
        'Cached',
        'TimedOut',
        'TriggerFailed'
      ],
      flowStates: [
        { header: 'Finished States' },
        { divider: '...' },
        'Failed',
        'Success',
        'Mapped',
        'Finished',
        'Cached',
        'Skipped',
        'TriggerFailed',
        'TimedOut',
        'Cancelled',
        { header: 'Scheduled - To Re-run Flow Run' },
        { divider: '...' },
        'Scheduled',
        { header: 'Pending States' },
        { divider: '...' },
        'Pending',
        'Paused'
      ]
    }
  },
  computed: {
    filteredStates() {
      if (this.dialogType === 'task run') {
        return this.taskStates.filter(state => state !== this.taskRun.state)
      } else {
        return this.flowStates.filter(state => state !== this.flowRun.state)
      }
    },
    checkVersion() {
      if (
        this.flowRun.flow.core_version[0] > 0 ||
        this.flowRun.flow.core_version[2] > 7 ||
        (this.flowRun.flow.core_version[2] > 6 &&
          this.flowRun.flow.core_version[4] > 2)
      ) {
        return true
      } else {
        return false
      }
    }
  },
  methods: {
    runLogMessage() {
      return `${this.dialogType} marked as ${this.selectedState} ${
        this.reason ? 'because "' + this.reason + '"' : ''
      } `
    },
    activeButton() {
      if (this.dialogType === 'task run') {
        if (this.taskRun.state === 'Running') return true
        return !!this.taskStates.includes(this.taskRun.state)
      } else if (this.dialogType === 'flow run') {
        return true
      }
    },
    async writeLogs() {
      const { data } = await this.$apollo.mutate({
        mutation: require('@/graphql/Update/writelogs.gql'),
        variables: {
          flowRunId: this.taskRun ? this.taskRun.flow_run.id : this.flowRun.id,
          taskRunId: this.taskRun ? this.taskRun.id : null,
          name: this.name,
          message: this.runLogMessage()
        }
      })
      return data && data.writeRunLogs && data.writeRunLogs.success
    },
    cancelFlowRun() {
      this.cancelLoad = true
      this.selectedState = 'Cancelled'
      this.allTasks = true
      this.toastedMessage =
        'Please try pressing cancel again. If the flow run has finished, use "Mark As" instead.'
      this.changeState()
    },
    async changeState() {
      try {
        this.markAsLoading = true
        const logSuccess = this.writeLogs()
        if (logSuccess) {
          if (
            this.dialogType === 'task run' ||
            (this.allTasks && this.flowRun.task_runs.length)
          ) {
            let taskState
            if (this.dialogType === 'task run') {
              taskState = {
                task_run_id: this.taskRun.id,
                version: this.taskRun.version,
                state: {
                  type: this.selectedState,
                  message: this.runLogMessage()
                }
              }
            } else {
              taskState = this.flowRun.task_runs.map(taskRun => {
                return {
                  version: taskRun.version,
                  task_run_id: taskRun.id,
                  state: {
                    type: this.selectedState,
                    message: this.runLogMessage()
                  }
                }
              })
            }
            const result = await this.$apollo.mutate({
              mutation: require('@/graphql/TaskRun/set-task-run-states.gql'),
              variables: {
                setTaskRunStatesInput: taskState
              }
            })
            this.setStateSuccessA =
              result?.data?.set_task_run_states?.states?.length
            if (!this.setStateSuccessA) {
              this.setStateError = true
            }
          }
          if (this.dialogType === 'flow run') {
            const result = await this.$apollo.mutate({
              mutation: require('@/graphql/TaskRun/set-flow-run-states.gql'),
              variables: {
                flowRunId: this.flowRun.id,
                version: this.flowRun.version,
                state: {
                  type: this.selectedState,
                  message: this.runLogMessage()
                }
              }
            })
            this.setStateSuccessB =
              result?.data?.set_flow_run_states?.states?.length
            if (!this.setStateSuccessB) {
              this.setStateError = true
            }
          }
        } else {
          this.setStateError = true
        }
      } catch (error) {
        this.setStateError = true
      }
      if (this.setStateError) {
        this.$toasted.show(this.toastedMessage, {
          containerClass: 'toast-typography',
          type: 'error',
          icon: 'error',
          action: {
            text: 'Close',
            onClick(e, toastObject) {
              toastObject.goAway(0)
            }
          },
          duration: 3000
        })
      }
      if (
        this.setStateSuccessA &&
        this.setStateSuccessB &&
        this.cancelLoad &&
        !this.setStateError
      ) {
        this.$toasted.show(
          'Flow run set for cancel.  This may take 30 seconds.',
          {
            containerClass: 'toast-typography',
            type: 'success',
            icon: 'check_circle',
            action: {
              text: 'Close',
              onClick(e, toastObject) {
                toastObject.goAway(0)
              }
            },
            duration: 3000
          }
        )
      }
      this.reset()
    },
    checkContinue() {
      if (this.selectedState) {
        this.e1 = 2
      }
    },
    reset() {
      this.markAsDialog = false
      this.markAsLoading = false
      this.reason = ''
      this.form = false
      this.setStateError = false
      this.e1 = 1
      this.selectedState = ''
      this.allTasks = false
      this.cancelLoad = false
      this.toastedMessage =
        'We hit a problem.  Please try marking the state again.'
      this.setStateSuccessA = false
      this.setStateSuccessB = false
      this.cancelLoad = false
    }
  }
}
