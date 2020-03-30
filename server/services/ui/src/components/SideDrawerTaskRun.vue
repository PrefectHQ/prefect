<script>
export default {
  props: {
    genericInput: {
      required: true,
      type: Object,
      validator: input => {
        return !!input.id
      }
    }
  },
  data() {
    return {
      taskRun: null
    }
  },
  apollo: {
    taskRun: {
      query: require('@/graphql/FlowRun/task-run-drawer.gql'),
      variables() {
        return { id: this.genericInput.id }
      },
      pollInterval: 1000,
      update: data => data.task_run_by_pk
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout
      v-if="$apollo.queries.taskRun.loading || !taskRun"
      align-center
      column
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>
    <v-layout v-else column>
      <v-flex xs 12>
        <div class="title">
          <router-link
            class="link"
            :to="{
              name: 'task-run',
              params: { id: taskRun.id }
            }"
          >
            {{ taskRun.flow_run.name }} - {{ taskRun.task.name
            }}<span v-if="taskRun.map_index > -1">
              ({{ taskRun.map_index }})</span
            >
          </router-link>
        </div>
      </v-flex>
      <v-flex xs12 class="mt-4">
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Task
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <router-link
              class="link"
              :to="{ name: 'task', params: { id: taskRun.task.id } }"
            >
              {{ taskRun.task.name }}
            </router-link>
          </v-flex>
        </v-layout>
        <v-layout v-if="taskRun.task.description" class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Task Description
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.task.description }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            State
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <v-icon small :color="taskRun.state" class="mr-1">
              brightness_1
            </v-icon>
            <span>{{ taskRun.state }}</span>
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Start Time
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.start_time | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            End Time
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.end_time | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Duration
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.duration | duration }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Heartbeat
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.heartbeat | displayDateTime }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Run Count
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.run_count }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Max Retries
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.task.max_retries }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Retry Delay
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.task.retry_delay | duration }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Message
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.state_message }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Result
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ taskRun.state_result }}
          </v-flex>
        </v-layout>
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.side-drawer-flow-runs {
  overflow-y: scroll;
}
</style>
