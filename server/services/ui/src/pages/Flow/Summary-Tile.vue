<script>
import CardTitle from '@/components/Card-Title'
import StackedLineChart from '@/components/Visualizations/StackedLineChart'
import { STATE_COLORS, STATE_PAST_TENSE } from '@/utils/states'
import { oneAgo } from '@/utils/dateTime'

export default {
  components: {
    CardTitle,
    StackedLineChart
  },
  props: {
    flowId: {
      type: String,
      default: () => null
    },
    fullHeight: {
      required: false,
      type: Boolean,
      default: () => false
    }
  },
  data() {
    return {
      dateFilters: [
        { name: '1 Hour', value: 'hour' },
        { name: '24 Hours', value: 'day' },
        { name: '7 Days', value: 'week' },
        { name: '30 Days', value: 'month' }
      ],
      loading: 0,
      selectedDateFilter: 'day',
      stateSegments: [],
      total: 0
    }
  },
  computed: {
    computedDateFilter() {
      return this.dateFilters.find(d => d.value == this.selectedDateFilter)
        .value
    },
    colors() {
      return STATE_COLORS
    },
    filteredStateSegments() {
      return this.stateSegments
        .filter(s => s.value > 0)
        .sort((sA, sB) => {
          return sA.value > sB.value ? -1 : sA.value < sB.value ? 1 : 0
        })
    },
    moreStateSegments() {
      return this.filteredStateSegments.slice(3)
    }
  },
  watch: {
    selectedDateFilter() {
      this.$apollo.queries.flowRunsAggregate.refetch()
    }
  },
  methods: {
    cursorPointer(event) {
      event.target.style.cursor = 'pointer'
    },
    humanLabel(label) {
      return STATE_PAST_TENSE[label]
    },
    statusStyle(state) {
      return {
        'border-radius': '50%',
        display: 'inline-block',
        'background-color': this.colors[state],
        height: '1rem',
        width: '1rem'
      }
    }
  },
  apollo: {
    flowRunsAggregate: {
      query: require('@/graphql/Flow/flow-runs.gql'),
      loadingKey: 'loading',
      variables() {
        return {
          flowId: this.flowId,
          updated: oneAgo(this.selectedDateFilter)
        }
      },
      pollInterval: 3000,
      update(data) {
        if (data.loading) return

        this.total = 0

        Object.keys(data).forEach(state => {
          let index = this.stateSegments.findIndex(s => s.label == state)
          if (index > -1) {
            this.stateSegments[index].value = data[state].aggregate.count
          } else {
            this.stateSegments.push({
              label: state,
              value: data[state].aggregate.count
            })
          }

          this.total += data[state].aggregate.count
        })
        return this.stateSegments
      }
    }
  }
}
</script>

<template>
  <v-card
    class="pa-2"
    tile
    :style="{
      height: fullHeight ? '100%' : 'auto'
    }"
  >
    <CardTitle title="Flow Runs Summary" icon="trending_up">
      <v-select
        slot="action"
        v-model="selectedDateFilter"
        class="time-interval-picker"
        :items="dateFilters"
        dense
        solo
        item-text="name"
        item-value="value"
        hide-details
        flat
      >
        <template v-slot:prepend-inner>
          <v-icon color="black" x-small>
            history
          </v-icon>
        </template>
      </v-select>
    </CardTitle>

    <v-card-text
      class="pb-0 pt-2 card-content d-flex align-center justify-center"
    >
      <div style="width: 100%;">
        <v-row no-gutters>
          <v-col class="subtitle-2 text-center">
            In the last {{ selectedDateFilter }}
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="5">
            <div class="text-center">
              <div class="font-weight-bold display-1" style="min-height: 36px;">
                <v-skeleton-loader
                  v-if="loading > 0"
                  type="heading"
                  class="centered-skeleton"
                />
                <v-tooltip v-else-if="filteredStateSegments.length > 0" bottom>
                  <template v-slot:activator="{ on }">
                    <span v-on="on">
                      <span class="hoverable">
                        {{ total.toLocaleString() }}
                      </span>
                    </span>
                  </template>
                  <div>
                    <div
                      v-for="segment in filteredStateSegments"
                      :key="segment.label"
                      class="d-flex align-center justify-space-between"
                    >
                      <span>
                        <span :style="statusStyle(segment.label)" class="mr-2">
                        </span>
                        <span>
                          {{ segment.value.toLocaleString() }}
                        </span>
                      </span>
                      <span class="ml-2">
                        {{ humanLabel(segment.label) }}
                      </span>
                    </div>
                  </div>
                </v-tooltip>
                <div v-else>0</div>
              </div>
              <div class="subtitle">flow runs</div>
            </div>
          </v-col>
          <v-col cols="2" class="d-flex align-center justify-center">
            <StackedLineChart
              :segments="stateSegments"
              :colors="colors"
              :width="50"
              vertical
            />
          </v-col>
          <v-col cols="5">
            <div class="text-center">
              <div class="font-weight-bold display-1" style="min-height: 36px;">
                <v-skeleton-loader
                  v-if="loading > 0"
                  type="heading"
                  class="centered-skeleton"
                />
                <v-tooltip v-else-if="filteredStateSegments.length > 0" bottom>
                  <template v-slot:activator="{ on }">
                    <span v-on="on">
                      <span class="hoverable">
                        {{
                          ((filteredStateSegments[0].value / total) * 100)
                            | roundTenths
                        }}
                      </span>
                      <span class="subtitle-2">%</span>
                    </span>
                  </template>
                  <div>
                    <div
                      v-for="segment in filteredStateSegments"
                      :key="segment.label"
                      class="d-flex align-center justify-space-between"
                    >
                      <span>
                        <span :style="statusStyle(segment.label)" class="mr-2">
                        </span>
                        <span>
                          {{
                            ((segment.value / total) * 100)
                              | roundTenths
                              | filterOnePercent
                          }}%
                        </span>
                      </span>
                      <span class="ml-2">
                        {{ humanLabel(segment.label) }}
                      </span>
                    </div>
                  </div>
                </v-tooltip>
              </div>
              <div class="subtitle">
                <v-skeleton-loader
                  v-if="loading > 0"
                  type="text"
                  class="centered-skeleton"
                />
                <div v-else-if="filteredStateSegments.length > 0">
                  {{ humanLabel(filteredStateSegments[0].label) }}
                </div>
              </div>
            </div>
          </v-col>
        </v-row>
      </div>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
.hoverable {
  border-bottom: 1px dotted #ddd;
  box-sizing: content-box;
}

.time-interval-picker {
  font-size: 0.85rem;
  margin: auto;
  margin-right: 0;
  max-width: 150px;
}
</style>

<style lang="scss">
.card-content {
  height: 254px;
  overflow-y: scroll;
}

.centered-skeleton {
  // stylelint-disable
  .v-skeleton-loader__bone {
    margin: auto !important;
  }
  // stylelint-enable
}
</style>
