<template>
  <ListItem>
    <div>
      <i class="item--icon pi pi-flow pi-2x" />

      <div>
        <div class="item--title subheader">
          {{ flow.name }}
        </div>
        <Tag
          v-for="tag in flow.tags"
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
    <Button color="primary">Quick run</Button>
  </ListItem>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import ListItem from '../ListItem/ListItem.vue'
import { Flow } from '@/objects'

class Props {
  flow = prop<Flow>({ required: true })
}

@Options({
  components: { ListItem }
})
export default class ListItemFlow extends Vue.with(Props) {}
</script>

<style lang="scss"></style>
