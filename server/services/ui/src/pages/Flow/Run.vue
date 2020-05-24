<script>
/* eslint-disable vue/no-v-html */

import difference from 'lodash.difference'
import jsBeautify from 'js-beautify'

import CardTitle from '@/components/Card-Title'
import JsonInput from '@/components/JsonInput'
import Parameters from '@/components/Parameters'
import PrefectSchedule from '@/components/PrefectSchedule'
import DateTime from '@/components/DateTime'
import { ERROR_MESSAGE as genericErrorMessage } from '@/utils/error'

import 'codemirror/addon/edit/matchbrackets'
import 'codemirror/addon/edit/closebrackets'
import 'codemirror/lib/codemirror.css'

const jsonFormatOptions = {
  indent_size: 2,
  space_in_empty_paren: true,
  preserve_newlines: false
}

export default {
  apollo: {
    flow: {
      query: require('@/graphql/Flow/run-flow.gql'),
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      pollInterval: 1000,
      update: data => data.flow_by_pk
    }
  },
  components: {
    CardTitle,
    JsonInput,
    Parameters,
    PrefectSchedule,
    DateTime
  },
  data() {
    return {
      // Flow provided by GraphQL query
      flow: null,

      // Parameters
      allParameters: null,
      errorInParameterInput: false,
      extraRequiredParameters: [],
      missingRequiredParameters: [],
      parameterInput: null,
      requiredParameters: null,

      // Context
      contextInfoOpen: false,
      contextInput: '{}',
      errorInContextInput: false,

      //Schedule
      scheduledStartDateTime: null,

      // Flow run name input
      flowRunName: '',

      // ID of newly-created flow run
      flowRunId: null,

      // Loading state
      loading: false,

      //DateTime component messages
      label: 'Scheduled Start Time',
      hint: 'Leave this field blank if you want to run the flow immediately.',
      warning:
        'Since this time is in the past, your flow will be scheduled to run immediately.'
    }
  },
  watch: {
    flow(newValue) {
      this.setParameterInput(newValue.parameters)
      this.collectParameterKeys(newValue.parameters)
    }
  },

  methods: {
    setSchedule(scheduledDateTime) {
      this.scheduledStartDateTime = scheduledDateTime
    },
    async run() {
      try {
        this.loading = true

        this.extraRequiredParameters = []
        this.missingRequiredParameters = []

        if (!this.validParameters()) return
        if (!this.validContext()) return

        const flowRunResponse = await this.$apollo.mutate({
          mutation: require('@/graphql/Mutations/create-flow-run.gql'),
          variables: {
            context:
              this.contextInput && this.contextInput.trim() !== ''
                ? JSON.parse(this.contextInput)
                : null,
            flowId: this.flow.id,
            flowRunName: this.flowRunName || null,
            parameters:
              this.parameterInput && this.parameterInput.trim() !== ''
                ? JSON.parse(this.parameterInput)
                : null,
            scheduledStartTime: this.scheduledStartDateTime
          }
        })

        this.flowRunId = flowRunResponse?.data?.create_flow_run?.id

        this.renderSuccessAlert()

        this.goToFlowRunPage()
      } catch (error) {
        this.showErrorAlert(genericErrorMessage)
        throw error
      } finally {
        this.loading = false
      }
    },
    collectParameterKeys(parameters) {
      // Collect all parameters and sort alphabetically by name
      this.allParameters = parameters.sort((a, b) => (a.name > b.name ? 1 : -1))

      // Collect all required parameters
      this.requiredParameters = parameters.reduce((accum, currentParam) => {
        if (currentParam.required) accum.push(currentParam.name)
        return accum
      }, [])
    },
    defaultParamText(param) {
      if (this.paramIsArray(param)) return 'Array'
      if (this.paramIsObject(param)) return 'Object'
      return param
    },
    extraParamsErrorMessage() {
      return `
          Extra flow parameters were supplied. Please remove the ${
            this.extraParameters.length == 1 ? 'parameter' : 'parameters'
          } ${this.sentencifyParamsList(this.extraParameters)} and try again.
        `
    },
    formatDefaultParamValue(defaultParamValue) {
      return jsBeautify(JSON.stringify(defaultParamValue), jsonFormatOptions)
    },
    formatParameterInput() {
      this.parameterInput = jsBeautify(this.parameterInput, jsonFormatOptions)
    },
    goToFlowRunPage() {
      this.$router.push({
        name: 'flow-run',
        params: { id: this.flowRunId }
      })
    },
    paramIsArray(param) {
      return Array.isArray(param)
    },
    paramIsObject(param) {
      return (
        typeof param === 'object' && param != null && !this.paramIsArray(param)
      )
    },
    renderSuccessAlert() {
      this.$toasted.success('Your flow run has been successfully scheduled.', {
        containerClass: 'toast-typography',
        action: {
          text: 'Close',
          onClick(e, toastObject) {
            toastObject.goAway(0)
          }
        },
        duration: 5000
      })
    },
    sentencifyParamsList(params) {
      // Sort parameters alphabetically and bold each parameter.
      const words = params.sort().map(param => `<b><i>${param}</i></b>`)

      // Return a sentence version of the params list.
      if (words.length === 1) {
        return words[0]
      } else if (words.length === 2) {
        return `${words[0]} and ${words[1]}`
      } else {
        words[words.length - 1] = `and ${words[words.length - 1]}`
        return words.join(', ')
      }
    },
    setParameterInput(parameters) {
      this.parameterInput = JSON.stringify(
        parameters.reduce((accum, currentParam) => {
          accum[currentParam.name] = currentParam.default
          return accum
        }, {})
      )

      this.formatParameterInput()
    },
    showErrorAlert(errorMessage) {
      this.$toasted.error(errorMessage, {
        containerClass: 'toast-typography',
        icon: 'error',
        action: {
          text: 'Close',
          onClick(e, toastObject) {
            toastObject.goAway(0)
          }
        },
        duration: 5000
      })
    },
    validContext() {
      if (!this.$refs.contextRef) {
        return true
      }

      // Check JSON using the JsonInput component's validation
      const jsonValidationResult = this.$refs.contextRef.validateJson()

      if (jsonValidationResult === 'SyntaxError') {
        this.errorInContextInput = true
        this.showErrorAlert(`
          There is a syntax error in your flow context JSON.
          Please correct the error and try again.
        `)
        return false
      }

      if (jsonValidationResult === 'MissingError') {
        this.errorInContextInput = true
        this.showErrorAlert('Please enter your flow context as a JSON object.')
        return false
      }

      return true
    },
    validParameters() {
      if (!this.$refs.parameterRef) {
        return true
      }

      // Check JSON using the JsonInput component's validation
      const jsonValidationResult = this.$refs.parameterRef.validateJson()

      if (jsonValidationResult === 'SyntaxError') {
        this.errorInParameterInput = true
        this.showErrorAlert(`
          There is a syntax error in your flow parameters JSON.
          Please correct the error and try again.
        `)
        return false
      }

      if (jsonValidationResult === 'MissingError') {
        this.errorInParameterInput = true
        this.showErrorAlert(
          'Please enter your flow parameters as a JSON object.'
        )
        return false
      }

      const parameters = JSON.parse(this.parameterInput)

      // Collect any missing required parameters
      this.missingRequiredParameters = difference(
        this.requiredParameters,
        Object.keys(parameters)
      )

      // Collect any extra parameters.
      this.extraParameters = difference(
        Object.keys(parameters),
        this.allParameters.map(param => param.name)
      )

      if (
        this.missingRequiredParameters.length === 0 &&
        this.extraParameters.length === 0
      ) {
        return true
      }

      this.errorInParameterInput = true
      if (this.missingRequiredParameters.length > 0) {
        this.showErrorAlert(`
          There are required flow parameters missing in the JSON payload.
          Please specify values for the missing parameters before running the flow.
        `)
      } else {
        this.showErrorAlert(this.extraParamsErrorMessage())
      }
      return false
    }
  }
}
</script>

<template>
  <v-container
    v-if="$apollo.queries.flow.loading || !flow"
    class="fill-height"
    fluid
    justify-center
  >
  </v-container>
  <v-container v-else class="fill-height" fluid justify-center>
    <v-layout
      align-content-start
      fill-height
      wrap
      :style="{ maxWidth: `${$vuetify.breakpoint.thresholds.md}px` }"
    >
      <v-flex xs12 sm4>
        <v-card tile class="mx-2 mt-1 mb-2">
          <CardTitle title="Run Details" icon="trending_up" />

          <v-card-text v-if="flow.archived">
            <v-alert
              class="mt-4"
              border="left"
              colored-border
              elevation="2"
              type="warning"
            >
              This flow is archived and cannot be run.
            </v-alert>
            <div class="py-4">
              For extra information, including how to unarchive this flow, check
              out the
              <router-link
                to="docs"
                target="_blank"
                href="https://docs.prefect.io/orchestration/concepts/flows.html#flow-versions-and-archiving"
              >
                Flow Versions and Archiving
              </router-link>
              section in our documentation.
            </div>
          </v-card-text>
          <v-card-text v-else>
            <div class="mb-4">
              <v-text-field
                v-model="flowRunName"
                label="Flow run name"
                hint="You can leave this field blank if desired. Prefect will
                instead generate a random name for your flow run."
                persistent-hint
              ></v-text-field>
            </div>
            <DateTime
              :label="label"
              :hint="hint"
              :warning="warning"
              @selectDateTime="setSchedule"
            />
            <div class="mb-6">
              <v-subheader class="pl-0 subheader-height font-weight-bold">
                SCHEDULE
              </v-subheader>
              <div v-if="!flow.schedules.length">
                No Schedule
              </div>
              <div v-if="flow.schedules.length && flow.schedules[0].active">
                Schedule Active
              </div>
              <div
                v-else-if="flow.schedules.length && !flow.schedules[0].active"
              >
                Schedule Inactive
              </div>
              <div
                v-if="flow.schedules.length && flow.schedules[0].active"
                class="mt-3"
              >
                <v-icon>query_builder</v-icon>
                <PrefectSchedule
                  class="ml-1 body-1"
                  :schedule="flow.schedules[0].schedule"
                />
              </div>
            </div>
            <div class="pb-6">
              <div
                class="pa-0 pr-3 position-relative"
                :hide-actions="missingRequiredParameters.length > 0"
              >
                <v-subheader class="pl-0 subheader-height font-weight-bold">
                  PARAMETERS
                </v-subheader>
              </div>
              <div v-if="allParameters && allParameters.length > 0">
                <Parameters
                  :parameters="allParameters"
                  :missing="missingRequiredParameters"
                ></Parameters>
              </div>
              <div v-else>
                No Parameters
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-flex>
      <v-flex xs12 sm8>
        <v-card tile class="ma-2 flow-root">
          <CardTitle title="Parameters" icon="notes">
            <template slot="action">
              <v-fade-transition>
                <v-icon
                  v-if="errorInParameterInput"
                  class="float-right mr-4"
                  color="error"
                >
                  error
                </v-icon>
              </v-fade-transition>
            </template>
          </CardTitle>
          <v-card-text class="px-2">
            <v-layout class="mb-3 position-relative" align-center>
              <div
                v-if="
                  !flow.archived && allParameters && allParameters.length > 0
                "
                class="width-100"
                :class="{
                  'ml-9': this.$vuetify.breakpoint.mdAndUp
                }"
              >
                <JsonInput
                  ref="parameterRef"
                  v-model="parameterInput"
                  data-cy="flow-run-parameter-input"
                  @input="errorInParameterInput = false"
                ></JsonInput>
              </div>
              <div v-else-if="flow.archived" class="px-2">
                This flow is archived and cannot be run.
              </div>
              <div v-else class="px-2 ma-auto">
                This flow does not require any parameters. Click "Run" to launch
                your flow!
              </div>
            </v-layout>
            <v-layout class="mt-7 mb-2">
              <v-btn
                class="vertical-button white--text ma-auto"
                color="primary"
                data-cy="submit-new-flow-run"
                fab
                large
                :loading="loading"
                elevation="2"
                @click="run"
              >
                <v-icon
                  class="mt-1 v-size--default"
                  :style="{
                    height: '24px',
                    'font-size': '24px',
                    'min-width': '24px'
                  }"
                >
                  fa-rocket
                </v-icon>
                <div>Run</div>
              </v-btn>
            </v-layout>
          </v-card-text>
        </v-card>
        <v-card tile class="mx-2 mt-6 flow-root">
          <CardTitle icon="list">
            <template slot="title">
              Context
              <v-menu
                v-model="contextInfoOpen"
                offset-y
                :close-on-content-click="false"
                open-on-hover
              >
                <template v-slot:activator="{ on }">
                  <div class="inline-block pr-4" v-on="on">
                    <v-icon
                      small
                      class="material-icons-outlined"
                      @focus="contextInfoOpen = true"
                      @blur="contextInfoOpen = false"
                    >
                      info
                    </v-icon>
                  </div>
                </template>
                <v-card tile class="pa-0" max-width="320">
                  <v-card-text class="pb-0">
                    <p>
                      (Optional) Provide
                      <strong>Context</strong> for your flow run to share
                      information between tasks without the need for explicit
                      task run arguments.
                    </p>
                    <p>
                      Refer to the
                      <a
                        href="https://docs.prefect.io/core/concepts/execution.html#context"
                        target="_blank"
                        rel="noopener noreferrer"
                        @click="contextInfoOpen = false"
                      >
                        documentation</a
                      >
                      <sup
                        ><v-icon x-small>
                          open_in_new
                        </v-icon></sup
                      >
                      for more details on Context.
                    </p>
                  </v-card-text>
                  <v-card-actions class="pt-0">
                    <v-spacer></v-spacer>
                    <v-btn small text @click="contextInfoOpen = false"
                      >Close</v-btn
                    >
                  </v-card-actions>
                </v-card>
              </v-menu>
              <v-fade-transition>
                <v-icon
                  v-if="errorInContextInput"
                  class="float-right mr-4"
                  color="error"
                >
                  error
                </v-icon>
              </v-fade-transition>
            </template>
          </CardTitle>
          <v-card-text class="px-2">
            <v-layout class="mb-3 position-relative" align-center>
              <div v-if="flow.archived" class="px-2">
                This flow is archived and cannot be run.
              </div>
              <div
                v-else
                class="width-100"
                :class="{
                  'ml-9': this.$vuetify.breakpoint.mdAndUp
                }"
              >
                <JsonInput
                  ref="contextRef"
                  v-model="contextInput"
                  height-auto
                  @input="errorInContextInput = false"
                ></JsonInput>
              </div>
            </v-layout>
          </v-card-text>
        </v-card>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.flow-root {
  display: flow-root;
}

.subheader-height {
  height: 24px;
}

.width-100 {
  width: 100%;
}
</style>

<style lang="scss">
.tab-height-custom {
  .v-tabs-bar {
    height: 36px !important;
  }
}
</style>
