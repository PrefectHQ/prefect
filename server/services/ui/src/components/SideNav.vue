<script>
import { mapMutations, mapGetters } from 'vuex'

const version = process.env.VUE_APP_PREFECT_VERSION
  ? process.env.VUE_APP_PREFECT_VERSION
  : 'development'

export default {
  data() {
    return {
      items: [],
      tzMenuOpen: false,
      confirm: false,
      version: version
    }
  },
  computed: {
    ...mapGetters('sideNav', ['isOpen']),
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
    width() {
      if (this.$vuetify.breakpoint.xsOnly) {
        return window.innerWidth
      }
      return '300'
    }
  },
  watch: {
    $route() {
      this.close()
    }
  },
  methods: {
    ...mapMutations('sideNav', ['toggle', 'close']),
    closeDialogAndMenu() {
      this.open = false
    }
  }
}
</script>

<template>
  <!-- We need both v-if and v-model because this vuetify component
  has mobile touch functionality that we want to preserve  -->
  <v-expand-x-transition>
    <v-navigation-drawer
      v-if="open"
      v-model="open"
      app
      clipped
      left
      temporary
      :width="width"
    >
      <div class="lists-wrapper">
        <v-list flat>
          <v-list-item class="side-nav-header">
            <v-list-item-content>
              <v-img
                height="40"
                contain
                class="logo"
                position="left"
                src="@/assets/logos/logo-full-color-horizontal.svg"
                alt="The Prefect Logo"
              />
            </v-list-item-content>
            <v-list-item-action>
              <v-btn icon small @click="close">
                <v-icon>close</v-icon>
              </v-btn>
            </v-list-item-action>
          </v-list-item>
          <v-list-item
            active-class="primary-active-class"
            :to="{
              name: 'dashboard'
            }"
            ripple
            exact
          >
            <v-list-item-action>
              <v-icon>view_quilt</v-icon>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title>Dashboard</v-list-item-title>
            </v-list-item-content>
          </v-list-item>

          <v-list-item
            active-class="primary-active-class"
            :to="{
              name: 'api'
            }"
            ripple
          >
            <v-list-item-action>
              <v-icon>vertical_split</v-icon>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title>Interactive API</v-list-item-title>
            </v-list-item-content>
          </v-list-item>

          <v-list-item
            active-class="primary-active-class"
            :to="{
              name: 'flow-version-groups'
            }"
            ripple
          >
            <v-list-item-action>
              <v-icon>timeline</v-icon>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title>Flow Version Groups</v-list-item-title>
            </v-list-item-content>
          </v-list-item>

          <v-list-item ripple target="_blank" href="https://docs.prefect.io">
            <v-list-item-action>
              <v-icon>library_books</v-icon>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title>Documentation</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-icon x-small>
                open_in_new
              </v-icon>
            </v-list-item-action>
          </v-list-item>

          <v-list-item ripple target="_blank" href="https://prefect.io/cloud">
            <v-list-item-action>
              <v-icon>cloud</v-icon>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title>Upgrade to Prefect Cloud</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-icon x-small>
                open_in_new
              </v-icon>
            </v-list-item-action>
          </v-list-item>
        </v-list>

        <v-list>
          <v-divider class="mt-4" />

          <v-list-item dense one-line>
            <v-list-item-content>
              <v-list-item-title class="">
                <v-row
                  class="overline grey--text text--darken-2 d-flex justify-center align-center"
                >
                  <v-col cols="5" class="text-center">
                    <div class="mb-2">
                      <img
                        style="max-width: 50px;"
                        src="@/assets/logos/prefect-core-mark-slate.svg"
                      />
                    </div>
                    <div>Prefect Server</div>
                    <div>{{ version }}</div>
                  </v-col>
                </v-row>
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </div>
    </v-navigation-drawer>
  </v-expand-x-transition>
</template>

<style lang="scss" scoped>
.lists-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: space-between;
  min-width: 300px;

  .v-list {
    padding: 0;
  }

  .side-nav-header {
    border-bottom: 2px solid #eee;
  }
}

.primary-active-class:not(.v-list-item--disabled) {
  color: var(--v-primary-base) !important;
}

.v-list-item--disabled {
  color: #aaa;
}
</style>
