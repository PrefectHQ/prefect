<template>
  <ol class="list">
    <slot>
      <ListItem>Item 1</ListItem>
      <ListItem>Item 2</ListItem>
      <ListItem>Item 3</ListItem>
    </slot>
  </ol>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import ListItem from './ListItem/ListItem.vue'

class Props {}

@Options({
  components: { ListItem }
})
export default class List extends Vue.with(Props) {}
</script>

<style lang="scss">
@use '@/styles/components/list.scss';
</style>
