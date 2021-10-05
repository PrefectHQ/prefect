<template>
  <div>
    <div class="search-bar">
      <Select
        v-model="search"
        name="Node search"
        search
        placeholder="Search for a task..."
      >
        <Option v-for="(value, key) in dataset" :key="key" :value="value.id">
          {{ value.name }}
        </Option>
      </Select>

      <Select v-model="selected" class="ml-2">
        <Option v-for="(value, key) in datasets" :key="key" :value="key">
          {{ key }}
        </Option>
      </Select>
    </div>

    <div>
      <Schematic ref="schematic" :items="dataset" />
    </div>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import { ref } from 'vue'

import Schematic from '../components/Schematic/Schematic.vue'
import { default as dataset1 } from '../util/schematics/62_nodes.json'
import { default as dataset2 } from '../util/schematics/50_linear_nodes.json'
import { default as dataset3 } from '../util/schematics/etl.json'
import { default as dataset4 } from '../util/schematics/1000_nodes.json'
import { default as dataset5 } from '../util/schematics/15_nodes.json'
import { default as dataset6 } from '../util/schematics/3_nodes.json'
import { default as dataset7 } from '../util/schematics/61_cluster_nodes.json'

@Options({
  components: { Schematic },
  watch: {
    dataset() {
      this.search = ''
    },
    search(val) {
      this.handleSelectSearchOption(this.dataset.find((d: any) => d.id == val))
    }
  }
})
export default class Schematics extends Vue {
  schematic = ref<InstanceType<typeof Schematic>>()

  selected: string = '3 Nodes: ETL'

  search: string = ''
  showOptions: boolean = false

  datasets: { [key: string]: any[] } = {
    '3 Nodes: ETL': dataset3,
    '50 Linear Nodes': dataset2,
    '62 Random Nodes': dataset1,
    '1000 Random Nodes': dataset4,
    '15 Random Nodes': dataset5,
    '3 Nodes': dataset6,
    '61 Cluster Nodes': dataset7
  }

  get dataset(): any[] {
    return this.datasets[this.selected]
  }

  handleSelectSearchOption(item: any): void {
    if (!item) return
    this.search = item.name
    ;(this.schematic as unknown as InstanceType<typeof Schematic>)?.panToNode(
      item
    )
  }

  handleSelectDataSet(key: string): void {
    this.selected = key
  }
}
</script>

<style lang="scss" scoped>
.search-bar {
  position: absolute;
  top: 50px;
  left: 100px;
  z-index: 2;
  display: flex;
}
</style>
