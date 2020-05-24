<script>
export default {
  data() {
    return {
      height: '0px',
      logo: false,
      welcome: false
    }
  },
  mounted() {
    setTimeout(() => {
      this.welcome = true
      this.logo = true

      setTimeout(() => {
        this.height = getComputedStyle(this.$refs['main-row']).height
      })
    }, 500)

    setTimeout(() => {
      this.$router.push({
        name: 'dashboard'
      })
    }, 3500)
  }
}
</script>

<template>
  <v-container class="text-center d-flex align-center justify-center h-80">
    <v-row
      no-gutters
      align="center"
      justify="center"
      :style="{ 'max-height': height }"
      class="transition-height"
    >
      <div ref="main-row">
        <transition-group name="fade" mode="out-in">
          <v-col
            v-if="welcome"
            key="welcome"
            class="headline w-100 pa-0"
            cols="12"
          >
            Welcome to
          </v-col>
          <v-col v-if="logo" key="logo" cols="12" class="w-100">
            <img
              class="ma-auto logo"
              src="@/assets/logos/prefect-core-mark-slate.svg"
            />
          </v-col>
        </transition-group>
      </div>
    </v-row>
  </v-container>
</template>

<style lang="scss" scoped>
.h-80 {
  min-height: calc(80vh - 64px) !important;
}

.transition-height {
  transition: max-height 500ms ease;
}

.w-100 {
  width: 100vw;
}

.logo {
  max-width: 700px;
  width: 100%;
}
</style>
