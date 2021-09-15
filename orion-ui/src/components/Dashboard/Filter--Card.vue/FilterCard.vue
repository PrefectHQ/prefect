<template>
  <Card class="button-card">
    <div class="d-flex justify-space-between">
      <div>Late</div>
      <i class="pi pi-filter-3-line pi-lg" />
    </div>
  </Card>
</template>

<script>
import { Vue } from 'vue-class-component'

class Props {}
export default class ListItem extends Vue.with(Props) {}
</script>

<style lang="scss">
@use '@/styles/components/button--card.scss';
</style>
