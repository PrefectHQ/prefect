<template>
  <list-item class="list-item--task-run d-flex align-start justify-start">
    <!-- For a later date... maybe -->
    <!-- :class="state + '-border'" -->

    <i
      class="item--icon pi text--grey-40 align-self-start"
      :class="`pi-${state}`"
    />
    <div
      class="
        item--title
        ml-2
        d-flex
        flex-column
        justify-center
        align-self-start
      "
    >
      <h2>
        {{ run.name }}
      </h2>

      <div class="tag-container nowrap d-flex align-bottom">
        <span
          class="run-state correct-text caption mr-1"
          :class="state + '-bg'"
        >
          {{ state }}
        </span>

        <Tag
          v-for="tag in tags"
          :key="tag"
          color="secondary-pressed"
          class="font--primary caption font-weight-semibold mr-1"
          icon="pi-label"
          flat
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div v-if="sub_flow_run" v-breakpoints="'sm'" class="ml-auto nowrap">
      <rounded-button class="mr-1">
        <i class="pi pi-flow-run pi-sm" />
        {{ sub_flow_run }}
      </rounded-button>
    </div>

    <div
      class="font--secondary item--duration"
      :class="sub_flow_run ? '' : 'ml-auto'"
    >
      {{ duration }}
    </div>
  </list-item>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { secondsToApproximateString } from '@/util/util'
import { TaskRun } from '@/objects'

class Props {
  run = prop<TaskRun>({ required: true })
}

@Options({})
export default class ListItemTaskRun extends Vue.with(Props) {
  sliceStart: number = Math.floor(Math.random() * 4)

  get state(): string {
    return this.run.state.toLowerCase()
  }

  get tags(): string[] {
    return this.run.tags
  }

  get reason(): string | null {
    return this.state == 'failed' ? 'Lorem ipsum dolorset atem' : null
  }

  get sub_flow_run(): string | null {
    return this.run.sub_flow_run_id ? 'Sub flow run' : null
  }

  get duration(): string {
    return this.state == 'pending' || this.state == 'scheduled'
      ? '--'
      : secondsToApproximateString(this.run.duration)
  }
}
</script>

<style lang="scss" scoped>
.item--tags {
  border-radius: 4px;
  display: inline-block;
  padding: 4px 8px;
}

.run-state {
  text-transform: capitalize;
}
</style>

<style lang="scss" scoped>
@use '@/styles/components/list-item--task-run.scss';
</style>
