<script>
import { mapGetters, mapMutations } from 'vuex'

export default {
  computed: {
    ...mapGetters('sideDrawer', ['showOpenButton']),
    buttonClasses() {
      return {
        'navigation-drawer-md-lg': this.$vuetify.breakpoint.mdAndUp,
        'navigation-drawer-sm': this.$vuetify.breakpoint.smAndDown
      }
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['open'])
  }
}
</script>

<template>
  <div v-if="showOpenButton" class="wrapper" :class="buttonClasses">
    <v-btn class="open-btn" color="primary" icon small fab @click="open">
      <v-icon>arrow_back_ios</v-icon>
    </v-btn>
  </div>
</template>

<style lang="scss" scoped>
.navigation-drawer-md-lg {
  margin-top: 64px !important;
}

.navigation-drawer-sm {
  margin-top: 56px !important;
}

.open-btn {
  border-bottom-right-radius: 0 !important;
  border-top-right-radius: 0 !important;
}

.wrapper {
  padding-top: 1rem;
  position: fixed;
  right: 0;
}
</style>
