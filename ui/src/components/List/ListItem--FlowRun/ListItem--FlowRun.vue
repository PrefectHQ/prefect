<template>
  <ListItem> {{ run.name }} - {{ run.id }} -- {{ run.state }} </ListItem>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import ListItem from '../ListItem/ListItem.vue'

class FlowRun {
  id!: string
  name!: string
  state!: string
  tags!: string[]
}

class Props {
  run = prop<FlowRun>({ required: true })
}

@Options({
  components: { ListItem }
})
export default class ListItemFlowRun extends Vue.with(Props) {}
</script>

<style lang="scss">
// @use '@/styles/components/list--item.scss';
</style>
