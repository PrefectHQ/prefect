<script>
import FlowRunPageGanttChart from '@/pages/FlowRunPageGanttChart'
import LogsCard from '@/components/LogsCard/LogsCard'
import SchematicTile from '@/pages/FlowRun/Schematic-Tile'

export default {
  components: {
    FlowRunPageGanttChart,
    LogsCard,
    SchematicTile
  },
  props: {
    flowRun: {
      type: Object,
      default: () => {}
    }
  },
  data() {
    return {
      tab: 'schematic'
    }
  },
  mounted() {}
}
</script>

<template>
  <v-card tile>
    <v-tabs v-model="tab">
      <v-tab href="#schematic" active-class="custom-tab-active">
        <v-icon left>account_tree</v-icon>
        Schematic
      </v-tab>
      <v-tab href="#chart" active-class="custom-tab-active">
        <v-icon left>bar_chart</v-icon>
        Gantt Chart
      </v-tab>

      <v-tab href="#logs" active-class="custom-tab-active">
        <v-icon left>format_align_left</v-icon>
        Logs
      </v-tab>

      <v-tab-item value="schematic">
        <SchematicTile />
      </v-tab-item>

      <v-tab-item value="chart">
        <FlowRunPageGanttChart :flow-run-id="$route.params.id" />
      </v-tab-item>

      <v-tab-item class="px-2" value="logs">
        <LogsCard
          entity="flow"
          :query="require('@/graphql/Logs/flow-run-logs.gql')"
          :query-for-scoping="
            require('@/graphql/Logs/flow-run-logs-scoping.gql')
          "
          query-key="flow_run_by_pk"
          :variables="{ id: $route.params.id }"
        />
      </v-tab-item>
    </v-tabs>
  </v-card>
</template>
