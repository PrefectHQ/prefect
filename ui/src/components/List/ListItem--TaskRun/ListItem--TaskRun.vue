<template>
  <ListItem> {{ run.name }} - {{ run.id }} -- {{ run.state }} </ListItem>
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

<style lang="scss">
// @use '@/styles/components/list--item.scss';
</style>
