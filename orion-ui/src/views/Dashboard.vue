<template>
  <div>
    <h1>Dashboard</h1>

    <router-link to="/schematics">Scematics</router-link>
    <row class="filter-row py-1" hide-scrollbars>
      <button-card
        v-for="filter in premadeFilters"
        :key="filter.label"
        class="filter-card-button"
        shadow="sm"
      >
        <div class="d-flex justify-space-between align-center px-1">
          <div>
            <span class="subheader">{{ filter.count }}</span>
            <span class="ml-1">{{ filter.label }}</span>
          </div>
          <i class="pi pi-filter-3-line pi-lg" />
        </div>
      </button-card>
    </row>

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
        <list>
          <flow-list-item
            v-for="flow in flowList"
            :key="flow.id"
            :flow="flow"
          />
        </list>
      </div>

      <div v-else-if="resultsTab == 'deployments'">
        <div class="caption my-2">Deployments</div>
        <list>
          <deployment-list-item
            v-for="deployment in deploymentList"
            :key="deployment.id"
            :deployment="deployment"
          />
        </list>
      </div>
      <div v-else-if="resultsTab == 'flow-runs'">
        <div class="caption my-2">Flow Runs</div>
        <list>
          <flow-run-list-item
            v-for="run in flowRunList"
            :key="run.id"
            :run="run"
          />
        </list>
      </div>

      <div v-else-if="resultsTab == 'task-runs'">
        <div class="caption my-2">Task Runs</div>
        <list>
          <task-run-list-item
            v-for="run in taskRunList"
            :key="run.id"
            :run="run"
          />
        </list>
      </div>
    </transition>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import { Flow, FlowRun, Deployment, TaskRun } from '../objects'

// Temporary imports for dummy data
import { default as flowList } from '@/util/objects/flows.json'
import { default as deploymentList } from '@/util/objects/deployments.json'
import { default as flowRunList } from '@/util/objects/flow_runs.json'
import { default as taskRunList } from '@/util/objects/task_runs.json'

@Options({
  components: {}
})
export default class Dashboard extends Vue {
  flowList: Flow[] = flowList
  deploymentList: Deployment[] = deploymentList
  flowRunList: FlowRun[] = flowRunList
  taskRunList: TaskRun[] = taskRunList

  premadeFilters: { label: string; count: number }[] = [
    { label: 'Failed Runs', count: 15 },
    { label: 'Late Runs', count: 25 },
    { label: 'Upcoming Runs', count: 75 }
  ]

  resultsTab: string = 'flows'

  sayHello(): void {
    alert('hello')
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

.filter-card-button {
  min-width: 300px;
  width: 100%;
}

.filter-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-gap: 16px;
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
