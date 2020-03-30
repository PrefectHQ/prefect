<script>
export default {
  props: {
    // Gain direct control over the render of this layout.
    // This is particularly useful when you want to load data before rendering the layout & its contents.
    controlShow: {
      type: Boolean,
      default: false,
      required: false
    },
    // Determine whether or not to render the layout.
    // Do nothing if controlShow is false.
    show: {
      type: Boolean,
      default: false,
      required: false
    }
  },
  data() {
    return {
      showPage: this.show || false
    }
  },
  watch: {
    show(val) {
      this.showPage = val
    }
  },
  mounted() {
    // Do nothing if the user wants programmatic control over the layout render.
    if (this.controlShow) return

    // Otherwise, fade-in the layout.
    setTimeout(() => {
      this.showPage = true
    }, 0)
  },
  beforeDestroy() {
    // Do nothing if the user wants programmatic control over the layout render.
    if (this.controlShow) return

    // Otherwise, fade out.
    this.showPage = false
  }
}
</script>

<template>
  <transition name="ml-fade">
    <v-container
      v-show="showPage"
      fluid
      justify-center
      :style="{ 'max-width': `${this.$vuetify.breakpoint.thresholds.lg}px` }"
    >
      <v-row>
        <v-col cols="12" class="text-center pb-2">
          <h1 class="display-1"><slot name="title"></slot></h1>
        </v-col>
      </v-row>
      <v-row v-if="$slots.subtitle">
        <v-col cols="12" class="text-center py-0">
          <div class="subtitle-1">
            <slot name="subtitle"></slot>
          </div>
        </v-col>
      </v-row>
      <v-row v-if="$slots.cta">
        <v-col cols="12" class="text-center mt-1 mb-2">
          <slot name="cta"></slot>
        </v-col>
      </v-row>
      <v-row v-if="$slots.alerts">
        <v-col cols="12">
          <slot name="alerts"></slot>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12">
          <slot></slot>
        </v-col>
      </v-row>
    </v-container>
  </transition>
</template>

<style lang="scss">
.ml-fade-enter-active,
.ml-fade-leave-active {
  transition: opacity 400ms;
}

.ml-fade-enter,
.ml-fade-leave-to {
  opacity: 0;
}
</style>
