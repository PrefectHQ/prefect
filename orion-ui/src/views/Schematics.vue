<template>
  <div>
    <div class="search-bar">
      <div class="search-input" tabindex="-1">
        <input
          v-model="search"
          type="text"
          name="Node search"
          class="px-2 py-1"
          placeholder="Search for a task..."
        />

        <div class="search-options" tabindex="-1">
          <div
            v-for="item in filteredDataset"
            :key="item.id"
            class="option px-2 py-1"
            tabindex="0"
            @click="handleSelectSearchOption(item)"
            @keyup.enter="handleSelectSearchOption(item)"
          >
            {{ item.name }}
          </div>
        </div>
      </div>

      <select v-model="selected" class="ml-2">
        <option v-for="(value, key) in datasets" :key="key" :value="key">
          {{ key }}
        </option>
      </select>
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
    }
  }
})
export default class Schematics extends Vue {
  schematic = ref<InstanceType<typeof Schematic>>()

  selected: string = '3 Nodes: ETL'

  search: string = ''
  showOptions: boolean = false

  datasets: { [key: string]: Items } = {
    '3 Nodes: ETL': dataset3,
    '50 Linear Nodes': dataset2,
    '62 Random Nodes': dataset1,
    '1000 Random Nodes': dataset4,
    '15 Random Nodes': dataset5,
    '3 Nodes': dataset6,
    '61 Cluster Nodes': dataset7
  }

  get dataset(): Items {
    return this.datasets[this.selected]
  }

  get filteredDataset(): Items {
    return this.dataset.filter((item: Item) =>
      item.name.toLowerCase().includes(this.search.toLowerCase())
    )
  }

  handleSelectSearchOption(item: Item) {
    this.search = item.name
    ;(this.schematic as unknown as InstanceType<typeof Schematic>)?.panToNode(
      item
    )
  }

  handleSelectDataSet(key: string) {
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

  .search-input {
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06), 0px 1px 3px rgba(0, 0, 0, 0.1);
    position: relative;
    width: 300px;

    input {
      border: thin solid var(--grey-4);
      border-radius: 4px;
      outline: none;
      transition: all 150ms;
      width: 100%;

      &:focus {
        outline: none;
        border: thin solid var(--primary);
        box-shadow: none;
      }
    }

    .search-options {
      box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.06),
        0px 1px 3px rgba(0, 0, 0, 0.1);
      display: none;
      left: 2px;
      position: absolute;
      max-height: 40vh;
      overflow: auto;
      width: calc(100% - 4px);

      .option {
        background-color: var(--white);
        cursor: pointer;
        transition: all 25ms;

        &:hover,
        &:focus {
          background-color: var(--primary);
          color: white;
        }
      }
    }

    &:focus,
    &:focus-within {
      .search-options {
        display: block;
      }
    }
  }
}
</style>
