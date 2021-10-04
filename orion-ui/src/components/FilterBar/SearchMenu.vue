<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content d-flex align-center justify-start pa-2">
      This is where a search menu goes
    </div>
  </Card>
</template>

<script lang="ts" setup></script>

<style lang="scss" scoped>
.menu {
  border-radius: 0;
  position: relative;

  .menu-content {
    border-top: 2px solid $grey-10;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
  }
}
</style>
