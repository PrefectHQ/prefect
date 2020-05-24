<script>
export default {
  props: {
    icon: {
      type: String,
      default: () => 'tab'
    },
    iconColor: {
      type: String,
      default: () => '#fff'
    },
    accentColor: {
      type: String,
      default: () => 'rgb(39, 177, 255)'
    },
    title: { type: String, default: () => '' },
    subtitle: { type: String, default: () => '' },
    underline: { type: String, default: () => '' },
    disabled: { type: Boolean, default: () => false }
  },
  computed: {
    iconStyle() {
      return {
        'background-color': this.disabled ? '#757575' : this.accentColor,
        color: this.iconColor
      }
    },
    cardStyle() {
      return {
        'background-color': this.disabled ? '#eee' : '#fff'
      }
    }
  }
}
</script>

<template>
  <v-container class="main-container relative">
    <v-container class="absolute placeholder-container">
      <v-container
        :style="iconStyle"
        class="absolute box icon-box elevation-4 d-flex justify-center"
      >
        <v-icon>{{ icon || 'check_circle' }}</v-icon>
      </v-container>
      <v-container
        :style="cardStyle"
        class="absolute box text-box elevation-2 d-flex flex-column pa-3 pl-0"
      >
        <div style="margin-left: 115px;">
          <div class="overline grey--text text--darken-3">
            {{ subtitle }}
          </div>
          <div :class="$vuetify.breakpoint.lgAndUp ? 'display-1' : 'title'">
            {{ title }}
          </div>
          <div class="overline grey--text">
            {{ underline }}
          </div>
        </div>
      </v-container>
    </v-container>
  </v-container>
</template>

<style lang="scss" scoped>
.relative {
  position: relative;
}

.absolute {
  position: absolute;
}

.main-container {
  max-width: 95%;
  min-height: 125px;
  text-align: right;

  .placeholder-container {
    bottom: -25px;
    left: 0;
    max-width: 600px;
    right: -25px;
    top: 0;
  }

  .box {
    border-radius: 4px;

    &.icon-box {
      height: 125px;
      left: -15px;
      min-height: unset;
      top: 0;
      width: 125px;
      z-index: 2;

      i {
        color: inherit;
        font-size: 75px;
      }
    }

    &.text-box {
      bottom: 0;
      min-height: 125px;
      min-width: 150px;
      right: 0;
      z-index: 1;
    }
  }
}
</style>
