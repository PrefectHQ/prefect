<template>
  <ListItem>
    <div>
      <i class="item--icon pi pi-flow-run pi-2x" />

      <div>
        <div class="item--title subheader">
          {{ run.name }}
        </div>

        <Tag :color="run.state.toLowerCase()" class="item--tags mr-1">
          <span class="run-state">{{ run.state.toLowerCase() }}</span>
        </Tag>

        <Tag
          v-for="tag in run.tags"
          :key="tag"
          color="secondary-pressed"
          class="item--tags mr-1"
          outlined
        >
          {{ tag }}
        </Tag>
      </div>
    </div>

    <div class="ml-auto caption-small mr-2"> Run chart placeholder </div>
    <i class="pi pi-Arrow-Right" />
  </ListItem>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import ListItem from '../ListItem/ListItem.vue'
import { FlowRun } from '@/objects'

class Props {
  run = prop<FlowRun>({ required: true })
}

@Options({
  components: { ListItem }
})
export default class ListItemFlowRun extends Vue.with(Props) {}
</script>

<style lang="scss" scoped>
.run-state {
  text-transform: capitalize;
}
</style>
