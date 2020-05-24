<script>
import { mapGetters, mapMutations } from 'vuex'

export default {
  components: {
    SideDrawerFlow: () => import('@/components/SideDrawerFlow.vue'),
    SideDrawerFlowRun: () => import('@/components/SideDrawerFlowRun.vue'),
    SideDrawerFlowRuns: () => import('@/components/SideDrawerFlowRuns.vue'),
    SideDrawerFlowVersions: () =>
      import('@/components/SideDrawerFlowVersions.vue'),
    SideDrawerRecentFailures: () =>
      import('@/components/SideDrawerRecentFailures'),
    SideDrawerUpcomingFlowRuns: () =>
      import('@/components/SideDrawerUpcomingFlowRuns.vue'),
    SideDrawerTask: () => import('@/components/SideDrawerTask.vue'),
    SideDrawerTaskRun: () => import('@/components/SideDrawerTaskRun.vue'),
    SideDrawerTaskRunState: () =>
      import('@/components/SideDrawerTaskRunState.vue')
  },
  data() {
    return {
      prevRoute: this.$route
    }
  },
  computed: {
    ...mapGetters('sideDrawer', ['isOpen', 'currentDrawer']),
    drawerClass() {
      return {
        'navigation-drawer-md-lg':
          this.$vuetify.breakpoint.lgOnly || this.$vuetify.breakpoint.mdOnly,
        'navigation-drawer-sm': this.$vuetify.breakpoint.smOnly
      }
    },
    open: {
      get() {
        return this.isOpen
      },
      set(value) {
        if (value === false) {
          this.close()
        }
      }
    },
    temporary() {
      return (
        this.$vuetify.breakpoint.smOnly ||
        this.$vuetify.breakpoint.mdOnly ||
        this.$vuetify.breakpoint.lgOnly
      )
    },
    width() {
      if (this.$vuetify.breakpoint.xsOnly) {
        return window.innerWidth
      }
      return '350'
    },
    height() {
      return '95vh'
    }
  },
  watch: {
    $route(val) {
      if (
        this.prevRoute.name !== val.name ||
        Object.entries(this.prevRoute.query).length !==
          Object.entries(val.query).length
      ) {
        this.close()
        this.clearDrawer()
      }
      this.prevRoute = val
    }
  },
  methods: {
    ...mapMutations('sideDrawer', ['clearDrawer', 'close'])
  }
}
</script>

<template>
  <!-- We need both v-if and v-model because this vuetify component
  has mobile touch functionality that we want to preserve  -->
  <v-navigation-drawer
    v-if="open && currentDrawer"
    v-model="open"
    app
    :class="drawerClass"
    clipped
    hide-overlay
    right
    stateless
    :temporary="temporary"
    :width="currentDrawer.props.width || width"
    :height="height"
  >
    <v-toolbar class="elevation-1 ml-0 pl-0 white--text" color="accent">
      <v-btn
        color="white"
        class="close-btn ml-0 mt-2 white--text"
        icon
        small
        fab
        @click="close"
      >
        <v-icon>arrow_forward_ios</v-icon>
      </v-btn>

      <v-spacer />

      <div v-if="currentDrawer.title">
        {{ currentDrawer.title }}
      </div>

      <v-spacer />

      <v-btn class="mx-0 px-0" color="white" icon text @click="clearDrawer">
        <v-icon>close</v-icon>
      </v-btn>
    </v-toolbar>

    <component
      :is="currentDrawer.type"
      v-if="currentDrawer"
      :generic-input="currentDrawer.props"
    />
  </v-navigation-drawer>
</template>

<style lang="scss" scoped>
.close-btn {
  border-bottom-left-radius: 0 !important;
  border-top-left-radius: 0 !important;
  left: 0;
  position: fixed;
  top: 0;
}

.navigation-drawer-md-lg {
  margin-top: 64px !important;
}

.navigation-drawer-sm {
  margin-top: 56px !important;
}
</style>
