<template>
  <div>
    <h2>Dashboard</h2>
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
