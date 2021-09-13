<template>
  <div>
    <h1>Dashboard</h1>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'

@Options({
  components: {}
})
export default class Dashboard extends Vue {
  sayHello(): void {
    console.log('hello!')
  }
}
</script>
