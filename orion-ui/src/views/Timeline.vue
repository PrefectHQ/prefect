<template>
  <div class="d-flex flex-column">
    <div class="d-flex">
      <select v-model="selected" :search="true" class="mr-2">
        <option v-for="run in flowRuns" :key="run.id" :value="run.id">
          {{ run.id }}
        </option>
      </select>

      <!-- <select v-model="interval">
        <option v-for="(value, key) in intervals" :key="key" :value="value">
          {{ value }}
        </option>
      </select> -->
      <!-- <Select v-model="selected" :search="true" class="mr-2">
        <Option v-for="(value, key) in datasets" :key="key" :value="key">
          {{ key }}
        </Option>
      </Select>

      <Select v-model="interval">
        <Option v-for="(value, key) in intervals" :key="key" :value="value">
          {{ value }}
        </Option>
      </Select> -->
    </div>

    <Timeline
      v-if="runs.length"
      :items="runs"
      :interval="interval"
      background-color="blue-5"
    />
  </div>
</template>

<script lang="ts">
import { FlowRun, TaskRun } from '@/objects'
import { Options, Vue } from 'vue-class-component'

import Timeline from '../components/Timeline/Timeline.vue'

@Options({
  components: { Timeline },
  watch: {
    async selected() {
      this.runs = await this.getTaskRuns()
    }
  }
})
export default class TimelineView extends Vue {
  selected: string | null = null

  interval: string = 'minute'
  intervals: string[] = ['second', 'minute', 'hour', 'day']

  runs: TaskRun[] = []
  flowRuns: FlowRun[] = []

  async getTaskRuns() {
    if (!this.selected) return
    console.log([this.selected])
    const runs = await fetch('http://localhost:8000/task_runs/filter', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        flow_runs: {
          ids: [this.selected]
        }
      })
    })

    return await runs.json()
  }

  async mounted() {
    const flow_runs = await fetch('http://localhost:8000/flow_runs/filter', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sort: 'EXPECTED_START_TIME_DESC'
      })
    })

    const result = await flow_runs.json()
    this.flowRuns = result
    console.log(this.flowRuns)

    console.log(
      'no state details',
      this.flowRuns.filter((r) => !r.state && r.state_type !== 'SCHEDULED')
    )
  }
}
</script>

<style lang="scss" scoped></style>
