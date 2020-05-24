<template>
  <v-container class="fill-height" fluid justify-center>
    <v-layout align-content-start fill-height wrap style="max-width: 1440px;">
      <v-flex class="w-100" xs-12>
        <slot name="first-row" />
      </v-flex>
      <v-flex sm6 md4>
        <slot name="tile1" />
      </v-flex>
      <v-flex sm6 md4>
        <slot name="tile2" />
      </v-flex>
      <v-flex sm12 md4>
        <slot name="tile3" />
      </v-flex>
      <v-flex sm12 md8>
        <slot name="table" />
      </v-flex>
      <v-flex sm12 md4>
        <slot name="activityBar" />
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.w-100 {
  width: 100%;
}
</style>
