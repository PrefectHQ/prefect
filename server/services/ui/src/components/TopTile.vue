<template>
  <v-card height="375px" class="ma-2 pb-0">
    <v-card-title class="top">
      <slot name="header" />
    </v-card-title>
    <v-card-text class="middle">
      <slot name="main" />
    </v-card-text>
    <v-card-actions class="bottom">
      <slot name="footer" />
    </v-card-actions>
  </v-card>
</template>

<style lang="scss" scoped>
.top {
  height: 75px;
}

.middle {
  height: 250px;
}

.bottom {
  border-top: 2px solid #ebf0f3;
  height: 50px;
  width: 100%;
}
</style>
