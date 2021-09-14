<template>
  <ListItem>
    <div>
      <i class="item--icon pi pi-task-run pi-2x" />

      <div>
        <div class="item--title subheader">
          {{ run.name }}
        </div>

        <div
          class="item--tags mr-1 correct-text"
          :class="{ [run.state.toLowerCase() + '-bg']: true }"
        >
          <span class="run-state">{{ run.state.toLowerCase() }}</span>
        </div>

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
import { TaskRun } from '@/objects'

class Props {
  run = prop<TaskRun>({ required: true })
}

@Options({
  components: { ListItem }
})
export default class ListItemTaskRun extends Vue.with(Props) {}
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
