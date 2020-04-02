<script>
import jsBeautify from 'js-beautify'

import CardTitle from '@/components/Card-Title'
import DurationSpan from '@/components/DurationSpan'

export default {
  components: {
    CardTitle,
    DurationSpan
  },
  props: {
    flowRun: {
      type: Object,
      default: () => {}
    }
  },
  data() {
    return {
      tab: 'overview'
    }
  },
  computed: {
    flowRunVersion() {
      return `Version ${this.flowRun.version}`
    },
    hasContext() {
      return (
        this.flowRun.context && Object.keys(this.flowRun.context).length > 0
      )
    },
    hasParameters() {
      return Object.keys(this.flowRun.parameters).length > 0
    }
  },
  methods: {
    formatJson(obj) {
      return jsBeautify(JSON.stringify(obj), {
        indent_size: 2,
        space_in_empty_paren: true,
        preserve_newlines: false
      })
    }
  }
}
</script>

<template>
  <v-card class="py-2" tile>
    <v-system-bar
      :color="flowRun.state"
      :data-cy="'details-tile-flow-run-state|' + flowRun.state.toLowerCase()"
      :height="5"
      absolute
    >
      <!-- We should include a state icon here when we've got those -->
      <!-- <v-icon>{{ flowRun.state }}</v-icon> -->
    </v-system-bar>

    <CardTitle v-if="hasParameters || hasContext" icon="trending_up">
      <v-row slot="title" no-gutters class="d-flex align-center">
        <v-col cols="8">
          <div class="text-truncate pb-1">
            {{ flowRun.name }}
          </div>
          <div class="subtitle-2 grey--text text--darken-2">
            {{ flowRunVersion }}
          </div>
        </v-col>
        <v-col cols="4">
          <div class="d-flex flex-column align-end">
            <v-btn
              depressed
              small
              tile
              icon
              class="button-transition w-100 d-flex justify-end"
              :color="tab == 'overview' ? 'primary' : ''"
              :style="{
                'border-right': `3px solid ${
                  tab == 'overview' ? 'var(--v-primary-base)' : '#fff'
                }`,
                'box-sizing': 'content-box'
              }"
              @click="tab = 'overview'"
            >
              Overview
              <v-icon small>timeline</v-icon>
            </v-btn>

            <v-btn
              v-if="hasParameters"
              depressed
              small
              tile
              icon
              class="button-transition w-100 d-flex justify-end"
              :color="tab == 'parameters' ? 'primary' : ''"
              :style="{
                'border-right': `3px solid ${
                  tab == 'parameters' ? 'var(--v-primary-base)' : '#fff'
                }`,
                'box-sizing': 'content-box'
              }"
              @click="tab = 'parameters'"
            >
              Parameters
              <v-icon small>notes</v-icon>
            </v-btn>

            <v-btn
              v-if="hasContext"
              depressed
              small
              tile
              icon
              class="button-transition w-100 d-flex justify-end"
              :color="tab == 'context' ? 'primary' : ''"
              :style="{
                'border-right': `3px solid ${
                  tab == 'context' ? 'var(--v-primary-base)' : '#fff'
                }`,
                'box-sizing': 'content-box'
              }"
              @click="tab = 'context'"
            >
              Context
              <v-icon small>list</v-icon>
            </v-btn>
          </div>
        </v-col>
      </v-row>
    </CardTitle>

    <CardTitle
      v-else
      :title="flowRun.name"
      icon="trending_up"
      :subtitle="flowRunVersion"
    />

    <v-card-text class="pl-12 card-content">
      <v-fade-transition hide-on-leave>
        <div v-if="tab === 'overview'">
          <v-list-item v-if="flowRun.state_message" dense class="px-0">
            <v-list-item-content>
              <v-list-item-subtitle class="caption">
                Last State Message
              </v-list-item-subtitle>
              <div class="subtitle-2">
                <v-tooltip top>
                  <template v-slot:activator="{ on }">
                    <span class="caption" v-on="on">
                      [{{ flowRun.state_timestamp | displayTime }}]:
                    </span>
                  </template>
                  <div>
                    {{ flowRun.state_timestamp | displayTimeDayMonthYear }}
                  </div>
                </v-tooltip>
                {{ flowRun.state_message }}
              </div>
            </v-list-item-content>
          </v-list-item>

          <v-list-item dense class="pa-0">
            <v-list-item-content>
              <v-list-item-subtitle class="caption">
                <v-row no-gutters>
                  <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                      <v-col cols="6" v-on="on">
                        Flow Run Version
                      </v-col>
                    </template>
                    <span
                      >The flow run version shows how many times a flow run has
                      changed states. This flow run has changed state
                      {{ flowRun.version }} times.</span
                    >
                  </v-tooltip>

                  <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                      <v-col
                        cols="6"
                        class="text-right font-weight-bold"
                        v-on="on"
                      >
                        {{ flowRunVersion }}
                      </v-col>
                    </template>
                    <span
                      >The flow run version shows how many times a flow run has
                      changed states. This flow run has changed state
                      {{ flowRun.version }} times.
                    </span>
                  </v-tooltip>
                </v-row>
                <v-row no-gutters>
                  <v-col v-if="flowRun.start_time" cols="6">
                    Scheduled Start Time
                  </v-col>
                  <v-col
                    v-if="flowRun.start_time"
                    cols="6"
                    class="text-right font-weight-bold"
                  >
                    <v-tooltip top>
                      <template v-slot:activator="{ on }">
                        <span v-on="on">
                          {{ flowRun.scheduled_start_time | displayTime }}
                        </span>
                      </template>
                      <div>
                        {{
                          flowRun.scheduled_start_time | displayTimeDayMonthYear
                        }}
                      </div>
                    </v-tooltip>
                  </v-col>
                  <v-col cols="6">
                    {{ flowRun.start_time ? 'Started' : 'Scheduled to start' }}
                  </v-col>
                  <v-col cols="6" class="text-right font-weight-bold">
                    <v-tooltip top>
                      <template v-slot:activator="{ on }">
                        <span v-on="on">
                          {{
                            flowRun.start_time
                              ? flowRun.start_time
                              : flowRun.scheduled_start_time | displayTime
                          }}
                        </span>
                      </template>
                      <div>
                        {{
                          flowRun.start_time
                            ? flowRun.start_time
                            : flowRun.scheduled_start_time
                              | displayTimeDayMonthYear
                        }}
                      </div>
                    </v-tooltip>
                  </v-col>
                </v-row>
                <v-row v-if="flowRun.end_time" no-gutters>
                  <v-col cols="6">
                    Ended
                  </v-col>
                  <v-col cols="6" class="text-right font-weight-bold">
                    <v-tooltip top>
                      <template v-slot:activator="{ on }">
                        <span v-on="on">
                          {{ flowRun.end_time | displayTime }}
                        </span>
                      </template>
                      <div>
                        {{ flowRun.end_time | displayTimeDayMonthYear }}
                      </div>
                    </v-tooltip>
                  </v-col>
                </v-row>
                <v-row v-if="flowRun.start_time" no-gutters>
                  <v-col cols="6">
                    Duration
                  </v-col>
                  <v-col cols="6" class="text-right font-weight-bold">
                    <span v-if="flowRun.duration">
                      {{ flowRun.duration | duration }}
                    </span>
                    <DurationSpan
                      v-else-if="flowRun.start_time"
                      :start-time="flowRun.start_time"
                    />
                    <span v-else>
                      <v-skeleton-loader type="text"></v-skeleton-loader>
                    </span>
                  </v-col>
                </v-row>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </div>
      </v-fade-transition>

      <v-fade-transition hide-on-leave>
        <code v-if="tab === 'parameters'" class="code-custom pa-3 my-3">{{
          formatJson(flowRun.parameters)
        }}</code>
      </v-fade-transition>

      <v-fade-transition hide-on-leave>
        <code v-if="tab === 'context'" class="code-custom pa-3 my-3">{{
          formatJson(flowRun.context)
        }}</code>
      </v-fade-transition>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
.card-content {
  max-height: 254px;
  overflow-y: scroll;
}

.code-custom {
  background-color: #fff;
  border: 1px solid #dedede;
  border-radius: 0;
  box-shadow: none;
  color: #666;
  font-size: 0.85em;
  width: 100%;

  &::before,
  &::after {
    content: '' !important;
  }
}
</style>
