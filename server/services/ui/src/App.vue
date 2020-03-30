<script>
import { mapMutations } from 'vuex'
import NavBar from '@/components/NavBar'
import SideNav from '@/components/SideNav'
import SideDrawer from '@/components/SideDrawer'
import SideDrawerOpenButton from '@/components/SideDrawerOpenButton'

export default {
  components: {
    NavBar,
    SideNav,
    SideDrawer,
    SideDrawerOpenButton
  },
  data() {
    return {
      error: null,
      reset: false,
      shown: true,
      wholeAppShown: true
    }
  },
  computed: {
    notFoundPage() {
      return this.$route.name === 'not-found'
    }
  },
  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeydown)
    window.removeEventListener('offline', this.handleOffline)
    window.removeEventListener('online', this.handleOnline)
  },
  created() {
    document.addEventListener('keydown', this.handleKeydown)
    window.addEventListener('offline', this.handleOffline)
    window.addEventListener('online', this.handleOnline)
  },
  methods: {
    ...mapMutations('sideDrawer', {
      clearDrawer: 'clearDrawer',
      closeSideDrawer: 'close'
    }),
    ...mapMutations('sideNav', { closeSideNav: 'close' }),
    handleKeydown(e) {
      if (e.key === 'Escape') {
        this.closeSideDrawer()
        this.closeSideNav()
      }
    },
    handleOffline() {
      // if the page isn't visible don't display a message
      if (document.hidden || document.msHidden || document.webkitHidden) return
      this.$toasted.show(
        'Your browser appears to be offline. We will attempt to reconnect every few seconds until a connection is established.',
        {
          containerClass: 'toast-typography',
          action: {
            text: 'Close',
            onClick(e, toastObject) {
              toastObject.goAway(0)
            }
          },
          duration: 5000
        }
      )
    },
    handleOnline() {
      // if the page isn't visible don't display a message
      if (document.hidden || document.msHidden || document.webkitHidden) return
      this.$toasted.show('Connection restored', {
        containerClass: 'toast-typography',
        action: {
          text: 'Close',
          onClick(e, toastObject) {
            toastObject.goAway(0)
          }
        },
        duration: 3000
      })
    }
  }
}
</script>

<template>
  <v-app class="app">
    <v-content>
      <NavBar />
      <SideNav />
      <v-fade-transition mode="out-in">
        <router-view v-if="shown" class="router-view" />
      </v-fade-transition>

      <v-container v-if="error" class="fill-height" fluid justify-center>
        <v-card>
          <v-card-text>{{ error }}</v-card-text>
        </v-card>
      </v-container>
    </v-content>
    <SideDrawer />
    <SideDrawerOpenButton />
  </v-app>
</template>

<style lang="scss">
@font-face {
  font-family: “Source Code Pro”;
  src: url('assets/fonts/SourceCodePro-Regular.otf.woff2') format('woff2');
}

html {
  font-size: 0.9rem !important;
  overflow-y: auto;
}

.app {
  background-color: var(--v-appBackground-base) !important;
}

.theme--light.v-app-bar.primary {
  background-image: linear-gradient(
    165deg,
    var(--v-primary-base),
    var(--v-prefect-base)
  );
}

.link {
  color: #0f4880;
  text-decoration: none;

  &:hover,
  &:active,
  &:focus {
    text-decoration: underline;
  }
}

.router-view {
  max-width: 100% !important;
}

.toast-typography {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}

/*
  Set the toasted alert's CLOSE button color.

  Note: .toasted appears *twice* in the selector to increase
  CSS specificity, which is needed to override the default
  blue-link color.

  This is a lighter alternative to setting !important, which
  should be used sparingly.
*/
.toasted.toasted.toasted-primary {
  .action {
    color: #fff;
  }
}
</style>

<style lang="scss">
/*
  This is the fade transition css class overrides
*/
.fade-enter-active {
  animation: fade 500ms;
}

.fade-leave-active {
  animation: fade 500ms reverse;
}

@keyframes fade {
  0% {
    opacity: 0;
  }

  100% {
    opacity: 1;
  }
}

// stylelint-disable
.vertical-button {
  &.v-btn--tile {
    height: auto !important;
  }

  .v-btn__content {
    flex-direction: column-reverse !important;
  }
}
//stylelint-enable

// stylelint-disable
.v-input--vertical .v-input__slot {
  flex-direction: column-reverse !important;

  .v-input--selection-controls__input {
    align-self: center;
    margin: auto !important;
  }

  .v-btn:not(.v-btn--round).v-size--small {
    height: unset !important;
  }
}
// stylelint-enable

// stylelint-disable
.theme--light.v-tabs-items {
  // stylelint-enable
  background-color: var(--v-appBackground-base) !important;
}

.tabs-hidden {
  // stylelint-disable
  .v-tabs-bar {
    display: none;
  }
  // stylelint-enable
}

.font-strikethrough {
  text-decoration: line-through !important;
}

.font-strikethrough-diagonal {
  position: relative;

  &::before {
    border-color: inherit;
    border-top: 1px solid;
    content: '';
    left: 0;
    position: absolute;
    right: 0;
    top: 50%;
    transform: rotate(-5deg);
  }
}

.tabs-border-bottom {
  .v-tabs-bar {
    border-bottom: 1px solid #ddd !important;
  }
}

.position-absolute {
  position: absolute !important;
}

.position-relative {
  position: relative !important;
}

.overflow-y-hidden {
  overflow-y: hidden;
}

.overflow-y-scroll {
  overflow-y: scroll;
}

.inline-block {
  display: inline-block;
}

.word-break-normal {
  word-break: normal;
}

.rounded-none {
  border-radius: 0 !important;
}
</style>
