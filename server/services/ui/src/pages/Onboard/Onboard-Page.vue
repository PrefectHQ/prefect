<template>
  <v-container fluid class="ma-0 pa-0">
    <v-row no-gutters>
      <v-col cols="12">
        <v-row align="center" justify="center" no-gutters>
          <v-col cols="12" class="h-100">
            <transition name="fade" mode="out-in">
              <router-view class="router-view" />
            </transition>
          </v-col>
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>

<style lang="scss" scoped>
.h-100 {
  min-height: calc(100vh - 64px) !important;
}

.logo {
  max-width: 800px;
  width: 100%;
}
</style>
