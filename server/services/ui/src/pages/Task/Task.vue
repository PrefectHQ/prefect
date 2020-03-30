<script>
import BreadCrumbs from '@/components/BreadCrumbs'
import DependenciesTile from '@/pages/Task/Dependencies-Tile'
import DetailsTile from '@/pages/Task/Details-Tile'
import SubPageNav from '@/layouts/SubPageNav'
import TaskRunHeartbeatTile from '@/pages/Task/TaskRunHeartbeat-Tile'
import TaskRunTableTile from '@/pages/Task/TaskRunTable-Tile'
import TileLayoutAlternate from '@/layouts/TileLayout-Alternate'
import TileLayoutFull from '@/layouts/TileLayout-Full'

export default {
  components: {
    BreadCrumbs,
    DependenciesTile,
    DetailsTile,
    SubPageNav,
    TaskRunHeartbeatTile,
    TaskRunTableTile,
    TileLayoutAlternate,
    TileLayoutFull
  },
  data() {
    return {
      loading: 0,
      tab: this.getTab(),
      taskId: this.$route.params.id
    }
  },
  computed: {
    hideOnMobile() {
      return { 'tabs-hidden': this.$vuetify.breakpoint.smAndDown }
    },
    dependencies() {
      if (!this.task) return []
      let upstream = this.task.upstream_edges.map(edge => {
        return {
          ...edge.upstream_task,
          downstream_edges: [],
          upstream_edges: []
        }
      })
      let downstream = this.task.downstream_edges.map(edge => {
        return {
          ...edge.downstream_task,
          downstream_edges: [],
          upstream_edges: [{ upstream_task: { id: this.taskId } }]
        }
      })

      return [this.task, ...upstream, ...downstream]
    },
    downstreamCount() {
      if (!this.task) return null
      return this.task.downstream_edges.length
    },
    upstreamCount() {
      if (!this.task) return null
      return this.task.upstream_edges.length
    }
  },
  watch: {
    tab(val) {
      let query = {}
      switch (val) {
        case 'schematic':
          query = { schematic: this.taskId }
          break
        case 'runs':
          query = { runs: '' }
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
  mounted() {
    if (!this.$route.query || !this.$route.query.schematic) {
      this.$router
        .replace({
          query: {
            schematic: this.taskId
          }
        })
        .catch(e => e)
    }
  },
  methods: {
    getTab() {
      if ('runs' in this.$route.query) return 'runs'
      return 'overview'
    }
  },
  apollo: {
    task: {
      query: require('@/graphql/Task/task.gql'),
      loadingKey: 'loading',
      variables() {
        return {
          id: this.taskId
        }
      },
      update: data => data.task_by_pk
    }
  }
}
</script>

<template>
  <v-sheet color="appBackground">
    <SubPageNav>
      <span slot="page-type">Task</span>
      <span
        slot="page-title"
        :style="
          loading !== 0
            ? {
                display: 'block',
                height: '28px',
                overflow: 'hidden',
                width: '400px'
              }
            : {}
        "
      >
        <span v-if="loading === 0">
          {{ task.name }}
        </span>
        <span v-else style="width: 500px;">
          <v-skeleton-loader type="heading" tile></v-skeleton-loader>
        </span>
      </span>

      <span
        slot="breadcrumbs"
        :style="
          loading !== 0
            ? {
                display: 'block',
                height: '21px',
                overflow: 'hidden',
                width: '500px'
              }
            : {}
        "
      >
        <BreadCrumbs
          v-if="task && loading === 0"
          :crumbs="[
            {
              route: { name: 'dashboard' },
              text: 'Dashboard'
            },
            {
              route: { name: 'flow', params: { id: task.flow.id } },
              text: task.flow.name
            }
          ]"
        ></BreadCrumbs>
        <v-skeleton-loader v-else type="text" />
      </span>
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
        <v-icon left>view_module</v-icon>
        Overview
      </v-tab>

      <v-tab href="#runs" :style="hideOnMobile">
        <v-icon left>trending_up</v-icon>
        Runs
      </v-tab>

      <!-- <v-tab href="#analytics" :style="hideOnMobile" disabled>
        <v-icon left>insert_chart_outlined</v-icon>
        Analytics
      </v-tab> -->

      <v-tab-item class="tab-full-height pa-0" value="overview">
        <TileLayoutAlternate>
          <DetailsTile
            slot="col-1-tile-1"
            :task="task"
            :loading="loading > 0"
          />

          <TaskRunHeartbeatTile slot="col-1-tile-2" :task-id="taskId" />

          <DependenciesTile
            slot="row-2-tile-1"
            :tasks="dependencies"
            :upstream-count="upstreamCount"
            :downstream-count="downstreamCount"
            :loading="loading > 0"
          />
        </TileLayoutAlternate>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="runs">
        <TileLayoutFull>
          <TaskRunTableTile
            slot="row-2-tile"
            :task-id="taskId"
            :loading="loading > 0"
          />
        </TileLayoutFull>
      </v-tab-item>
    </v-tabs>

    <v-bottom-navigation v-if="$vuetify.breakpoint.smAndDown" fixed>
      <v-btn @click="tab = 'overview'">
        Overview
        <v-icon>view_module</v-icon>
      </v-btn>

      <v-btn @click="tab = 'runs'">
        Runs
        <v-icon>trending_up</v-icon>
      </v-btn>

      <!-- <v-btn disabled @click="tab = 'analytics'">
        Analytics
        <v-icon>insert_chart_outlined</v-icon>
      </v-btn> -->
    </v-bottom-navigation>
  </v-sheet>
</template>

<style lang="scss">
.tab-full-height {
  min-height: 80vh;
}
</style>
