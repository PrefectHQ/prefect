<template>
  <div class="d-flex flex-column">
    <div class="d-flex">
      <select v-model="selected" :search="true" class="mr-2">
        <option v-for="(value, key) in datasets" :key="key" :value="key">
          {{ key }}
        </option>
      </select>

      <select v-model="interval">
        <option v-for="(value, key) in intervals" :key="key" :value="value">
          {{ value }}
        </option>
      </select>
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
    <Timeline :items="dataset" :interval="interval" background-color="blue-5" />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'

import Timeline from '../components/Timeline/Timeline.vue'
import { default as dataset1 } from '../util/schematics/62_nodes.json'
import { default as dataset2 } from '../util/schematics/50_linear_nodes.json'
import { default as dataset3 } from '../util/schematics/etl.json'
import { default as dataset4 } from '../util/schematics/1000_nodes.json'
import { default as dataset5 } from '../util/schematics/15_nodes.json'
import { default as dataset6 } from '../util/schematics/3_nodes.json'
import { default as dataset7 } from '../util/schematics/61_cluster_nodes.json'
import { default as dataset8 } from '../util/schematics/25_nodes_time_corrected.json'

@Options({
  components: { Timeline }
})
export default class TimelineView extends Vue {
  selected: string = '25 Nodes'

  search: string = ''
  showOptions: boolean = false

  interval: string = 'minute'
  intervals: string[] = ['second', 'minute', 'hour', 'day']

  datasets: { [key: string]: Items } = {
    '3 Nodes: ETL': dataset3,
    '50 Linear Nodes': dataset2,
    '62 Random Nodes': dataset1,
    '1000 Random Nodes': dataset4,
    '15 Random Nodes': dataset5,
    '3 Nodes': dataset6,
    '61 Cluster Nodes': dataset7,
    '25 Nodes': dataset8
  }

  get dataset(): Items {
    return this.datasets[this.selected]
  }

  mounted() {
    console.log(this.datasets)
  }
}
</script>

<style lang="scss" scoped></style>
