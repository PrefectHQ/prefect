<template>
  <ListItem> {{ flow.name }} - {{ flow.id }} </ListItem>
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

<style lang="scss">
// @use '@/styles/components/list--item.scss';
</style>
