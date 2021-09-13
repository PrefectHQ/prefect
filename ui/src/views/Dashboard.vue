<template>
  <div>
    <h1>Dashboard</h1>

    <h2>Flows</h2>
    <List>
      <FlowListItem v-for="flow in flowList" :key="flow.id" :flow="flow" />
    </List>

    <h2>Deployments</h2>
    <List>
      <DeploymentListItem
        v-for="d in deploymentList"
        :key="d.id"
        :deployment="d"
      />
    </List>

    <h2>Flow Runs</h2>
    <List>
      <FlowRunListItem v-for="run in flowRunList" :key="run.id" :run="run" />
    </List>

    <h2>Task Runs</h2>
    <List>
      <TaskRunListItem v-for="run in taskRunList" :key="run.id" :run="run" />
    </List>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import List from '@/components/List/List.vue'
import FlowListItem from '@/components/List/ListItem--Flow/ListItem--Flow.vue'
import DeploymentListItem from '@/components/List/ListItem--Deployment/ListItem--Deployment.vue'
import FlowRunListItem from '@/components/List/ListItem--FlowRun/ListItem--FlowRun.vue'
import TaskRunListItem from '@/components/List/ListItem--TaskRun/ListItem--TaskRun.vue'
import { Flow, FlowRun, Deployment, TaskRun } from '../objects'

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
    TaskRunListItem
  }
})
export default class Dashboard extends Vue {
  flowList: Flow[] = flowList
  deploymentList: Deployment[] = deploymentList
  flowRunList: FlowRun[] = flowRunList
  taskRunList: TaskRun[] = taskRunList

  sayHello(): void {
    console.log('hello!')
  }
}
</script>
