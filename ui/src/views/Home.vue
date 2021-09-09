<template>
  <div class="px-8">
    <h1>Home</h1>
  </div>
</template>

<script lang="ts">
import { Options, Vue } from 'vue-class-component'

@Options({
  components: {}
})
export default class Home extends Vue {
  sayHello(): void {
    console.log('hello!')
  }
}
</script>
