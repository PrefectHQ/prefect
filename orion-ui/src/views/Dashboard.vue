<template>
  <div>
    <h1>Dashboard</h1>

    <div class="chart-card px-2 py-1">
      <div class="subheader">Run History</div>
      <RunHistoryChart :data="buckets" background-color="blue-5" />
    </div>

    <Tabs v-model="resultsTab" class="mt-5">
      <Tab href="flows">
        <i class="pi pi-flow pi-lg mr-1" />
        Flows
        <span class="result-badge" :class="{ active: resultsTab == 'flows' }">
          {{ flowList.length }}
        </span>
      </Tab>
      <Tab href="deployments">
        <i class="pi pi-deployment pi-lg mr-1" />
        Deployments
        <span
          class="result-badge"
          :class="{ active: resultsTab == 'deployments' }"
        >
          {{ deploymentList.length }}
        </span>
      </Tab>
      <Tab href="flow-runs">
        <i class="pi pi-flow-run pi-lg mr-1" />
        Flow Runs
        <span
          class="result-badge"
          :class="{ active: resultsTab == 'flow-runs' }"
        >
          {{ flowRunList.length }}
        </span>
      </Tab>
      <Tab href="task-runs">
        <i class="pi pi-task-run pi-lg mr-1" />
        Task Runs
        <span
          class="result-badge"
          :class="{ active: resultsTab == 'task-runs' }"
        >
          {{ taskRunList.length }}
        </span>
      </Tab>
    </Tabs>

    <transition name="fade" mode="out-in">
      <div v-if="resultsTab == 'flows'">
        <div class="caption my-2">Flows</div>
        <List>
          <FlowListItem v-for="flow in flowList" :key="flow.id" :flow="flow" />
        </List>
      </div>

      <div v-else-if="resultsTab == 'deployments'">
        <div class="caption my-2">Deployments</div>
        <List>
          <DeploymentListItem
            v-for="deployment in deploymentList"
            :key="deployment.id"
            :deployment="deployment"
          />
        </List>
      </div>
      <div v-else-if="resultsTab == 'flow-runs'">
        <div class="caption my-2">Flow Runs</div>
        <List>
          <FlowRunListItem
            v-for="run in flowRunList"
            :key="run.id"
            :run="run"
          />
        </List>
      </div>

      <div v-else-if="resultsTab == 'task-runs'">
        <div class="caption my-2">Task Runs</div>
        <List>
          <TaskRunListItem
            v-for="run in taskRunList"
            :key="run.id"
            :run="run"
          />
        </List>
      </div>
    </transition>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import List from '@/components/List/List.vue'
import FlowListItem from '@/components/List/ListItem--Flow/ListItem--Flow.vue'
import DeploymentListItem from '@/components/List/ListItem--Deployment/ListItem--Deployment.vue'
import FlowRunListItem from '@/components/List/ListItem--FlowRun/ListItem--FlowRun.vue'
import TaskRunListItem from '@/components/List/ListItem--TaskRun/ListItem--TaskRun.vue'
import {
  default as RunHistoryChart,
  Bucket
} from '@/components/RunHistoryChart/RunHistoryChart.vue'

import { Flow, FlowRun, Deployment, TaskRun } from '../objects'
import { default as dataset_1 } from '@/util/run_history/24_hours.json'
import { default as dataset_2 } from '@/util/run_history/design.json'

// Temporary imports for dummy data
import { default as flowList } from '@/util/objects/flows.json'
import { default as deploymentList } from '@/util/objects/deployments.json'
import { default as flowRunList } from '@/util/objects/flow_runs.json'
import { default as taskRunList } from '@/util/objects/task_runs.json'

@Options({
  components: {
    List,
    FlowListItem,
    DeploymentListItem,
    FlowRunListItem,
    TaskRunListItem,
    RunHistoryChart
  }
})
export default class Dashboard extends Vue {
  buckets: Bucket[] = dataset_2

  flowList: Flow[] = flowList
  deploymentList: Deployment[] = deploymentList
  flowRunList: FlowRun[] = flowRunList
  taskRunList: TaskRun[] = taskRunList

  resultsTab: string = 'flows'

  sayHello(): void {
    console.log('hello!')
  }
}
</script>

<style lang="scss" scoped>
.result-badge {
  border-radius: 16px;
  padding: 4px 16px;
  transition: 150ms all;

  &.active {
    background-color: $primary;
    color: $white;
  }
}

.chart-card {
  background-color: $white;
  box-shadow: $box-shadow-sm;
  border-radius: 4px;
  height: 250px;

  display: flex;
  flex-direction: column;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
