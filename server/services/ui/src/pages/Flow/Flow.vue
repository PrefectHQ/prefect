<script>
import Actions from '@/pages/Flow/Actions'
import BreadCrumbs from '@/components/BreadCrumbs'
import DetailsTile from '@/pages/Flow/Details-Tile'
import ErrorsTile from '@/pages/Flow/Errors-Tile'
import FlowRunHeartbeatTile from '@/pages/Flow/FlowRunHeartbeat-Tile'
import FlowRunTableTile from '@/pages/Flow/FlowRunTable-Tile'
import RunTiles from '@/pages/Flow/Run'
import SchematicTile from '@/pages/Flow/Schematic-Tile'
import Settings from '@/pages/Flow/Settings'
import SubPageNav from '@/layouts/SubPageNav'
import SummaryTile from '@/pages/Flow/Summary-Tile'
import TasksTableTile from '@/pages/Flow/TasksTable-Tile'
import TileLayout from '@/layouts/TileLayout'
import TileLayoutFull from '@/layouts/TileLayout-Full'
import UpcomingRunsTile from '@/pages/Flow/UpcomingRuns-Tile'
import VersionsTile from '@/pages/Flow/Versions-Tile'

export default {
  components: {
    Actions,
    BreadCrumbs,
    DetailsTile,
    ErrorsTile,
    FlowRunHeartbeatTile,
    FlowRunTableTile,
    RunTiles,
    SchematicTile,
    Settings,
    SubPageNav,
    SummaryTile,
    TasksTableTile,
    TileLayout,
    TileLayoutFull,
    UpcomingRunsTile,
    VersionsTile
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
    $route() {
      this.tab = this.getTab()
    },
    tab(val) {
      let query = {}
      switch (val) {
        case 'schematic':
          query = { schematic: '' }
          break
        case 'runs':
          query = { runs: '' }
          break
        case 'tasks':
          query = { tasks: '' }
          break
        case 'versions':
          query = { versions: '' }
          break
        case 'run':
          query = { run: '' }
          break
        case 'settings':
          query = { settings: '' }
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
      if ('runs' in this.$route.query) return 'runs'
      if ('tasks' in this.$route.query) return 'tasks'
      if ('versions' in this.$route.query) return 'versions'
      if ('run' in this.$route.query) return 'run'
      if ('settings' in this.$route.query) return 'settings'
      return 'overview'
    }
  },
  apollo: {
    flow: {
      query: require('@/graphql/Flow/flow.gql'),
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      pollInterval: 3000,
      update: data => data.flow_by_pk
    }
  }
}
</script>

<template>
  <v-sheet v-if="flow" color="appBackground">
    <SubPageNav>
      <span slot="page-type">Flow</span>
      <span slot="page-title">
        {{ flow.name }}
      </span>

      <BreadCrumbs
        slot="breadcrumbs"
        :crumbs="[
          {
            route: { name: 'dashboard' },
            text: 'Dashboard'
          }
        ]"
      ></BreadCrumbs>

      <Actions
        slot="page-actions"
        :flow="flow"
        :scheduled="flow.schedules.length > 0"
        :archived="!!flow.archived"
      />
    </SubPageNav>

    <v-tabs
      v-if="flow"
      v-model="tab"
      class="px-6 mx-auto tabs-border-bottom"
      :class="hideOnMobile"
      style="max-width: 1440px;"
      light
    >
      <v-tabs-slider color="blue"></v-tabs-slider>

      <v-tab href="#overview" :style="hideOnMobile" data-cy="flow-overview-tab">
        <v-icon left>view_module</v-icon>
        Overview
      </v-tab>

      <v-tab href="#tasks" :style="hideOnMobile" data-cy="flow-tasks-tab">
        <v-icon left>fiber_manual_record</v-icon>
        Tasks
      </v-tab>

      <v-tab href="#runs" :style="hideOnMobile" data-cy="flow-runs-tab">
        <v-icon left>trending_up</v-icon>
        Runs
      </v-tab>

      <v-tab
        href="#schematic"
        :style="hideOnMobile"
        data-cy="flow-schematic-tab"
      >
        <v-icon left>account_tree</v-icon>
        Schematic
      </v-tab>

      <v-tab href="#versions" :style="hideOnMobile" data-cy="flow-versions-tab">
        <v-icon left>loop</v-icon>
        Versions
      </v-tab>

      <!-- <v-tab href="#analytics" :style="hideOnMobile" disabled>
        <v-icon left>insert_chart_outlined</v-icon>
        Analytics
      </v-tab> -->

      <v-tab href="#run" :style="hideOnMobile" data-cy="flow-run-tab">
        <v-icon left>fa-rocket</v-icon>
        Run
      </v-tab>

      <v-spacer />

      <v-tab href="#settings" :style="hideOnMobile" data-cy="flow-settings-tab">
        <v-icon left>settings</v-icon>
        Settings
      </v-tab>

      <v-tab-item class="tab-full-height pa-0" value="overview">
        <TileLayout>
          <DetailsTile slot="row-1-col-1-tile-1" :flow="flow" full-height />

          <SummaryTile
            slot="row-1-col-2-tile-1"
            :flow-id="flow.id"
            full-height
          />

          <UpcomingRunsTile
            slot="row-1-col-3-tile-1"
            :flow="flow"
            full-height
          />

          <ErrorsTile
            slot="row-1-col-4-tile-1"
            :flow-id="flow.id"
            full-height
          />

          <FlowRunHeartbeatTile
            slot="row-2-col-1-row-4-tile-1"
            :flow-id="flow.id"
          />
        </TileLayout>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="tasks">
        <TileLayoutFull>
          <TasksTableTile slot="row-2-tile" :flow-id="flow.id" />
        </TileLayoutFull>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="runs">
        <TileLayoutFull>
          <FlowRunTableTile slot="row-2-tile" :flow-id="flow.id" />
        </TileLayoutFull>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="schematic">
        <TileLayoutFull>
          <SchematicTile slot="row-2-tile" />
        </TileLayoutFull>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="versions">
        <TileLayoutFull>
          <VersionsTile
            slot="row-2-tile"
            :flow-id="flow.id"
            :version="flow.version"
          />
        </TileLayoutFull>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="run">
        <RunTiles />
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="settings">
        <TileLayoutFull>
          <Settings slot="row-2-tile" :flow="flow" />
        </TileLayoutFull>
      </v-tab-item>
    </v-tabs>

    <v-bottom-navigation v-if="$vuetify.breakpoint.smAndDown" fixed>
      <v-btn @click="tab = 'overview'">
        Overview
        <v-icon>view_module</v-icon>
      </v-btn>

      <v-btn @click="tab = 'tasks'">
        Tasks
        <v-icon>fiber_manual_record</v-icon>
      </v-btn>

      <v-btn @click="tab = 'runs'">
        Runs
        <v-icon>trending_up</v-icon>
      </v-btn>

      <v-btn @click="tab = 'schematic'">
        Schematic
        <v-icon>account_tree</v-icon>
      </v-btn>

      <v-btn @click="tab = 'versions'">
        Versions
        <v-icon>loop</v-icon>
      </v-btn>

      <!-- <v-btn disabled @click="tab = 'analytics'">
        Analytics
        <v-icon>insert_chart_outlined</v-icon>
      </v-btn> -->

      <v-btn @click="tab = 'run'">
        Run
        <v-icon>fa-rocket</v-icon>
      </v-btn>

      <v-btn @click="tab = 'settings'">
        Settings
        <v-icon>settings</v-icon>
      </v-btn>
    </v-bottom-navigation>
  </v-sheet>
</template>

<style lang="scss">
.tab-full-height {
  min-height: 80vh;
}
</style>
