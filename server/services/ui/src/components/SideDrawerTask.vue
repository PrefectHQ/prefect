<script>
export default {
  filters: {
    typeClass: val => val.split('.').pop()
  },
  props: {
    genericInput: {
      required: true,
      type: Object,
      validator: input => {
        return !!input.taskId
      }
    }
  },
  data() {
    return {
      task: null
    }
  },
  apollo: {
    task: {
      query: require('@/graphql/Task/task-drawer.gql'),
      variables() {
        return { id: this.genericInput.taskId }
      },
      pollInterval: 1000,
      update: data => data.task_by_pk
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout
      v-if="$apollo.loading || !task"
      align-center
      column
      justify-center
    >
      <v-progress-circular indeterminate color="primary" />
    </v-layout>
    <v-layout v-else column>
      <v-flex xs12>
        <div class="title">
          <router-link
            class="link"
            :to="{
              name: 'task',
              params: { id: task.id }
            }"
          >
            {{ task.name }}
          </router-link>
        </div>
        <div v-if="task.description" class="subtitle-1">
          {{ task.description }}
        </div>
      </v-flex>
      <v-flex xs12 class="mt-4">
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Flow
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <router-link
              class="link"
              :to="{ name: 'flow', params: { id: task.flow.id } }"
            >
              {{ task.flow.name }}
            </router-link>
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Latest Run State
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            <span v-if="task.task_runs.length" class="pr-1">
              <v-icon small :color="task.task_runs[0].state">
                brightness_1
              </v-icon>
            </span>
            {{ task.task_runs.length ? task.task_runs[0].state : 'No Runs' }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Mapped
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ task.mapped ? 'Yes' : 'No' }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Slug
          </v-flex>
          <v-flex id="slug" xs6 class="text-right body-1 word-wrap">
            {{ task.slug }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Max Retries
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ task.max_retries | number }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Retry Delay
          </v-flex>
          <v-flex xs6 class="text-right body-1">
            {{ task.retry_delay | duration }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Trigger
          </v-flex>
          <v-flex xs6 class="text-right body-1 word-wrap">
            {{ task.trigger }}
          </v-flex>
        </v-layout>
        <v-layout class="my-2">
          <v-flex xs6 class="text-left body-1 font-weight-medium">
            Class
          </v-flex>
          <v-flex xs6 class="text-right body-1 word-wrap">
            {{ task.type | typeClass }}
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

.word-wrap {
  word-wrap: break-word;
}
</style>
