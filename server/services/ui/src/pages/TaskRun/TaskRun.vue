<script>
import Actions from '@/pages/TaskRun/Actions'
import BreadCrumbs from '@/components/BreadCrumbs'
import DetailsTile from '@/pages/TaskRun/Details-Tile'
import LogsCard from '@/components/LogsCard/LogsCard'
import DependenciesTile from '@/pages/TaskRun/Dependencies-Tile'
import SubPageNav from '@/layouts/SubPageNav'
import TaskRunHeartbeatTile from '@/pages/TaskRun/TaskRunHeartbeat-Tile'
import TileLayout from '@/layouts/TileLayout'
import TileLayoutFull from '@/layouts/TileLayout-Full'

export default {
  components: {
    Actions,
    BreadCrumbs,
    DependenciesTile,
    DetailsTile,
    LogsCard,
    SubPageNav,
    TaskRunHeartbeatTile,
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
    },
    dependencies() {
      if (!this.taskRun) return []
      let upstream = this.taskRun.task.upstream_edges.map(
        edge => edge.upstream_task.id
      )
      let downstream = this.taskRun.task.downstream_edges.map(
        edge => edge.downstream_task.id
      )
      return [this.taskRun.task.id, ...upstream, ...downstream]
    },
    downstreamCount() {
      if (!this.taskRun) return null
      return this.taskRun.task.downstream_edges.length
    },
    upstreamCount() {
      if (!this.taskRun) return null
      return this.taskRun.task.upstream_edges.length
    }
  },
  watch: {
    tab(val) {
      let query = {}
      switch (val) {
        case 'logs':
          query = { logId: '' }
          break
        default:
          break
      }
      this.$router
        .replace({
          query: query
        })
        .catch(e => e)
    },
    taskRun(val) {
      if (!val) return
      if (
        !this.$route.query ||
        (!this.$route.query.schematic && !this.$route.query.logId)
      ) {
        this.$router
          .replace({
            query: {
              schematic: this.taskRun.task.id
            }
          })
          .catch(e => e)
      }
    }
  },
  methods: {
    getTab() {
      if ('logId' in this.$route.query) return 'logs'
      return 'overview'
    }
  },
  apollo: {
    taskRun: {
      query: require('@/graphql/TaskRun/task-run.gql'),
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      pollInterval: 1000,
      update: data => data.task_run_by_pk
    },
    parent: {
      query: require('@/graphql/TaskRun/parent.gql'),
      variables() {
        return {
          taskId: this.taskRun ? this.taskRun.task.id : null,
          flowRunId: this.taskRun ? this.taskRun.flow_run.id : null
        }
      },
      pollInterval: 1000,
      update: data => (data.task_run ? data.task_run.length : null)
    }
  }
}
</script>

<template>
  <v-sheet v-if="taskRun" color="appBackground">
    <SubPageNav>
      <span slot="page-type">Task Run</span>
      <span slot="page-title">
        {{ taskRun.flow_run.name }} - {{ taskRun.task.name
        }}<span v-if="taskRun.map_index > -1">
          (Mapped Child {{ taskRun.map_index }})</span
        >

        <span v-else-if="parent > 1"> (Parent) </span>
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
              params: { id: taskRun.flow_run.flow.id }
            },
            text: taskRun.flow_run.flow.name
          },
          {
            route: {
              name: 'flow-run',
              params: { id: taskRun.flow_run.id }
            },
            text: taskRun.flow_run.name
          }
        ]"
      ></BreadCrumbs>

      <Actions slot="page-actions" :task-run="taskRun" />
    </SubPageNav>

    <v-tabs
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

      <v-tab href="#logs" :style="hideOnMobile">
        <v-icon left>format_align_left</v-icon>
        Logs
      </v-tab>

      <v-tab-item class="tab-full-height pa-0" value="overview">
        <TileLayout>
          <DetailsTile slot="row-2-col-1-row-1-tile-1" :task-run="taskRun" />

          <TaskRunHeartbeatTile
            slot="row-2-col-1-row-4-tile-1"
            :task-run-id="$route.params.id"
          />

          <DependenciesTile
            slot="row-2-col-2-row-3-tile-1"
            :flow-run-id="taskRun.flow_run.id"
            :task-ids="dependencies"
            :upstream-count="upstreamCount"
            :downstream-count="downstreamCount"
          />
        </TileLayout>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="logs">
        <TileLayoutFull>
          <LogsCard
            slot="row-2-tile"
            class="py-2 mt-4"
            entity="task"
            :query="require('@/graphql/Logs/task-run-logs.gql')"
            :query-for-scoping="
              require('@/graphql/Logs/task-run-logs-scoping.gql')
            "
            query-key="task_run_by_pk"
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
