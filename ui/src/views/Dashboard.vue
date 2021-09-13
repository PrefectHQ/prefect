<template>
  <div>
    <h1>Dashboard</h1>
    <List />
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'
import List from '@/components/List/List.vue'

@Options({
  components: { List }
})
export default class Dashboard extends Vue {
  sayHello(): void {
    console.log('hello!')
  }
}
</script>
