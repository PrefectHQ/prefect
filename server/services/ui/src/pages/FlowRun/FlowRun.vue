<script>
import Actions from '@/pages/FlowRun/Actions'
import BreadCrumbs from '@/components/BreadCrumbs'
import DetailsTile from '@/pages/FlowRun/Details-Tile'
import FlowRunPageGanttChart from '@/pages/FlowRun/GanttChart-Tile'
import LogsCard from '@/components/LogsCard/LogsCard'
import SchematicTile from '@/pages/FlowRun/Schematic-Tile'
import SubPageNav from '@/layouts/SubPageNav'
import TaskRunHeartbeatTile from '@/pages/FlowRun/TaskRunHeartbeat-Tile'
import TaskRunTableTile from '@/pages/FlowRun/TaskRunTable-Tile'
import TileLayout from '@/layouts/TileLayout'
import TileLayoutFull from '@/layouts/TileLayout-Full'

export default {
  components: {
    Actions,
    BreadCrumbs,
    DetailsTile,
    FlowRunPageGanttChart,
    LogsCard,
    SchematicTile,
    SubPageNav,
    TaskRunHeartbeatTile,
    TaskRunTableTile,
    TileLayout,
    TileLayoutFull
  },
  data() {
    return {
      tab: this.getTab()
    }
  },
  computed: {
    hideOnMobile() {
      return { 'tabs-hidden': this.$vuetify.breakpoint.smAndDown }
    }
  },
  watch: {
    tab(val) {
      let query = {}
      switch (val) {
        case 'schematic':
          query = { schematic: '' }
          break
        case 'logs':
          query = { logId: '' }
          break
        case 'chart':
          query = { chart: '' }
          break
        default:
          break
      }
      this.$router
        .replace({
          query: query
        })
        .catch(e => e)
    }
  },
  methods: {
    getTab() {
      if ('schematic' in this.$route.query) return 'schematic'
      if ('logId' in this.$route.query) return 'logs'
      if ('chart' in this.$route.query) return 'chart'
      return 'overview'
    }
  },
  apollo: {
    flowRun: {
      query: require('@/graphql/FlowRun/flow-run.gql'),
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      pollInterval: 1000,
      update: data => data.flow_run_by_pk
    }
  }
}
</script>

<template>
  <v-sheet v-if="flowRun" color="appBackground">
    <SubPageNav>
      <span slot="page-type">Flow Run</span>
      <span slot="page-title">
        {{ flowRun.name }}
      </span>

      <BreadCrumbs
        slot="breadcrumbs"
        :crumbs="[
          {
            route: { name: 'dashboard' },
            text: 'Dashboard'
          },
          {
            route: {
              name: 'flow',
              params: { id: flowRun.flow.id }
            },
            text: flowRun.flow.name
          }
        ]"
      ></BreadCrumbs>

      <Actions slot="page-actions" :flow-run="flowRun" />
    </SubPageNav>

    <v-tabs
      v-if="flowRun"
      v-model="tab"
      class="px-6 mx-auto tabs-border-bottom"
      :class="hideOnMobile"
      style="max-width: 1440px;"
      light
    >
      <v-tabs-slider color="blue"></v-tabs-slider>

      <v-tab href="#overview" :style="hideOnMobile">
        <v-icon left>trending_up</v-icon>
        Overview
      </v-tab>

      <v-tab href="#schematic" :style="hideOnMobile">
        <v-icon left>account_tree</v-icon>
        Schematic
      </v-tab>

      <v-tab href="#chart" :style="hideOnMobile">
        <v-icon left>bar_chart</v-icon>
        Gantt Chart
      </v-tab>

      <v-tab href="#logs" :style="hideOnMobile" data-cy="flow-run-logs-tab">
        <v-icon left>format_align_left</v-icon>
        Logs
      </v-tab>

      <v-tab-item class="tab-full-height pa-0" value="overview">
        <TileLayout>
          <DetailsTile slot="row-2-col-1-row-1-tile-1" :flow-run="flowRun" />

          <TaskRunHeartbeatTile
            slot="row-2-col-1-row-4-tile-1"
            :flow-run-id="$route.params.id"
          />

          <TaskRunTableTile
            slot="row-2-col-2-row-3-tile-1"
            :flow-run-id="flowRun.id"
          />
        </TileLayout>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="schematic">
        <TileLayoutFull>
          <SchematicTile slot="row-2-tile" />
        </TileLayoutFull>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="chart">
        <v-card class="pa-2 mt-2" tile>
          <FlowRunPageGanttChart :flow-run-id="$route.params.id" />
        </v-card>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="logs">
        <TileLayoutFull>
          <LogsCard
            slot="row-2-tile"
            class="py-2 mt-4"
            entity="flow"
            :query="require('@/graphql/Logs/flow-run-logs.gql')"
            :query-for-scoping="
              require('@/graphql/Logs/flow-run-logs-scoping.gql')
            "
            query-key="flow_run_by_pk"
            :variables="{ id: $route.params.id }"
          />
        </TileLayoutFull>
      </v-tab-item>
    </v-tabs>

    <v-bottom-navigation v-if="$vuetify.breakpoint.smAndDown" fixed>
      <v-btn @click="tab = 'overview'">
        Overview
        <v-icon>view_module</v-icon>
      </v-btn>

      <v-btn @click="tab = 'schematic'">
        Schematic
        <v-icon>account_tree</v-icon>
      </v-btn>

      <v-btn @click="tab = 'chart'">
        Gantt Chart
        <v-icon>account_tree</v-icon>
      </v-btn>

      <v-btn @click="tab = 'logs'">
        Logs
        <v-icon>format_align_left</v-icon>
      </v-btn>
    </v-bottom-navigation>
  </v-sheet>
</template>

<style lang="scss">
.custom-tab-active {
  background-color: #c8e1ff !important;
}

.tab-full-height {
  min-height: 80vh;
}
</style>
