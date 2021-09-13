<template>
  <ListItem> {{ deployment.name }} - {{ deployment.id }} </ListItem>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import ListItem from '../ListItem/ListItem.vue'

class Deployment {
  id!: string
  name!: string
  tags!: string[]
}

class Props {
  deployment = prop<Deployment>({ required: true })
}

@Options({
  components: { ListItem }
})
export default class ListItemDeployment extends Vue.with(Props) {}
</script>

<style lang="scss">
// @use '@/styles/components/list--item.scss';
</style>
