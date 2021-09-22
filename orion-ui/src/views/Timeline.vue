<template>
  <div class="d-flex flex-column">
    <div class="d-flex">
      <select v-model="selected" :search="true" class="mr-2">
        <option v-for="run in flowRuns" :key="run.id" :value="run.id">
          {{ run.id }}
        </option>
      </select>

      <Button icon="arrow-left-s-line" height="30px" width="30px" />

      <Button icon="arrow-right-s-line" height="30px" width="30px" />

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
      :max-end-time="endTime"
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
      this.startTaskRunInterval()
      this.startFlowRunInterval()
    }
  }
})
export default class TimelineView extends Vue {
  selected: string | string[] | null = null

  interval: ReturnType<typeof setInterval> | null = null

  runs: TaskRun[] = []
  flowRuns: FlowRun[] = []

  get flowRun(): undefined | FlowRun {
    return this.flowRuns?.find((r) => r.id == this.selected)
  }

  get endTime(): undefined | string {
    return this.flowRun?.end_time
  }

  async startTaskRunInterval(): Promise<void> {
    if (this.selected && typeof this.selected == 'string') {
      this.runs = await this.getTaskRuns(this.selected)
      this.$router.push({ params: { id: this.selected } })
    }

    if (this.flowRun?.state_type !== 'RUNNING') return
    this.interval = setInterval(async () => {
      if (this.selected && typeof this.selected == 'string') {
        this.runs = await this.getTaskRuns(this.selected)
      }
    }, 3000)
  }

  async getFlowRun(id: string) {
    const run = await fetch(`http://localhost:8000/flow_runs/${id}`)

    const result = await run.json()

    const index = this.flowRuns.findIndex((r) => r.id == result.id)

    if (index) {
      this.flowRuns[index] = result
    }
  }

  async startFlowRunInterval() {
    if (!this.flowRun) return
    if (this.interval) clearInterval(this.interval)

    console.log(this.flowRun)
    if (this.flowRun.state_type == 'RUNNING') {
      this.interval = setInterval(async () => {
        if (this.selected && typeof this.selected == 'string') {
          await this.getFlowRun(this.selected)
        }
      }, 3000)
    }
  }

  async getTaskRuns(id: string) {
    if (!this.selected) return
    // TODO: Move polling to global utility functions that we can turn on/off
    const runs = await fetch('http://localhost:8000/task_runs/filter', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        flow_runs: {
          id: {
            any_: [id]
          }
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

    if (this.$route.params.id) {
      this.selected = this.$route.params.id
    }
  }
}
</script>

<style lang="scss" scoped></style>
