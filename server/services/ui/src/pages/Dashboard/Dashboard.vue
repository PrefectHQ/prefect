<script>
import ErrorsTile from '@/pages/Dashboard/Errors-Tile'
import FlowRunHeartbeatTile from '@/pages/Dashboard/FlowRunHeartbeat-Tile'
import SummaryTile from '@/pages/Dashboard/Summary-Tile'
import FlowTableTile from '@/pages/Dashboard/FlowTable-Tile'
import UpcomingRunsTile from '@/pages/Dashboard/UpcomingRuns-Tile'
import FailuresTile from '@/pages/Dashboard/Failures-Tile'
import SubPageNav from '@/layouts/SubPageNav'
import TileLayout from '@/layouts/TileLayout'
import ApiHealthcheckTile from '@/pages/Dashboard/ApiHealthcheck-Tile'

export default {
  components: {
    ErrorsTile,
    FailuresTile,
    FlowRunHeartbeatTile,
    FlowTableTile,
    SubPageNav,
    SummaryTile,
    TileLayout,
    UpcomingRunsTile,
    ApiHealthcheckTile
  },
  data() {
    return {
      loading: 0,
      previousParams: { flows: { flows: '' }, agents: { agents: '' } },
      tab: this.getTab(),
      tabs: [
        {
          name: 'Overview',
          target: 'overview',
          icon: 'view_quilt'
        },
        {
          name: 'Flows',
          target: 'flows',
          icon: 'timeline'
        }
      ]
    }
  },
  computed: {
    hideOnMobile() {
      return { 'tabs-hidden': this.smAndDown }
    },
    smAndDown() {
      return this.$vuetify?.breakpoint?.smAndDown
    }
  },
  watch: {
    tab(val, prev) {
      let query = {}

      switch (val) {
        case 'flows':
          query = this.previousParams.flows
          break
        default:
          break
      }

      this.previousParams[prev] = this.$route.query
      this.$router.replace({ query }).catch(e => e)
    },
    $route(val) {
      if (Object.keys(val.query).length === 0 && this.tab !== 'overview') {
        this.tab = 'overview'
      }
    }
  },
  methods: {
    getTab() {
      if (!this.$route?.query) return 'overview'
      if ('flows' in this.$route.query) return 'flows'
      return 'overview'
    }
  }
}
</script>

<template>
  <v-sheet color="appBackground">
    <SubPageNav>
      <span slot="page-type">Dashboard</span>
      <span
        slot="page-title"
        style="height: 28px;
        overflow: hidden;"
      >
        <span v-if="loading === 0" style="text-transform: capitalize;">
          {{ tab }}
        </span>
        <span v-else>
          <v-skeleton-loader type="heading" tile></v-skeleton-loader>
        </span>
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

      <v-tab
        v-for="tb in tabs"
        :key="tb.target"
        :data-cy="`dashboard-${tb.target}-tab`"
        :href="`#${tb.target}`"
        :style="hideOnMobile"
      >
        <v-icon left :size="tb.iconSize || 'medium'">{{ tb.icon }}</v-icon>
        {{ tb.name }}
      </v-tab>

      <v-tab-item class="tab-full-height pa-0" value="overview">
        <TileLayout>
          <SummaryTile slot="row-1-col-1-tile-1" full-height />

          <FailuresTile slot="row-1-col-2-tile-1" />

          <UpcomingRunsTile slot="row-1-col-3-tile-1" full-height />

          <FlowRunHeartbeatTile slot="row-2-col-1-row-2-tile-1" />

          <ErrorsTile slot="row-2-col-2-row-2-tile-1" full-height />

          <ApiHealthcheckTile slot="row-2-col-2-row-2-tile-2" />
        </TileLayout>
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="flows">
        <FlowTableTile v-if="tab == 'flows'" class="mx-3 my-6" />
      </v-tab-item>

      <v-tab-item class="tab-full-height" value="analytics">
        Nothing to see here :)
      </v-tab-item>
    </v-tabs>

    <v-bottom-navigation v-if="smAndDown" fixed>
      <v-btn v-for="tb in tabs" :key="tb.target" @click="tab = tb.target">
        {{ tb.name }}
        <v-icon>{{ tb.icon }}</v-icon>
      </v-btn>
    </v-bottom-navigation>
  </v-sheet>
</template>

<style lang="scss">
.tab-full-height {
  min-height: 100vh;
}
</style>
