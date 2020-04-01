<script>
export default {
  props: {
    icon: {
      type: String,
      required: false,
      default: () => ''
    },
    params: {
      type: Object,
      required: false,
      default: () => {}
    },
    iconClass: {
      type: String,
      required: false,
      default: () => ''
    },
    iconColor: {
      type: String,
      required: false,
      default: () => ''
    },
    loading: {
      type: Boolean,
      required: false,
      default: () => false
    },
    subtitle: {
      type: String,
      required: false,
      default: () => null
    },
    title: {
      type: String,
      required: false,
      default: () => ''
    }
  }
}
</script>

<template>
  <div>
    <v-list-item dense class="px-0" :to="params">
      <v-list-item-avatar class="mr-2">
        <v-icon :color="iconColor" :class="iconClass">
          {{ icon }}
        </v-icon>
      </v-list-item-avatar>
      <v-list-item-content :class="$slots['title'] ? 'py-0' : ''">
        <v-list-item-title class="title pb-1">
          <slot v-if="$slots['title']" name="title" />
          <v-row v-else no-gutters class="d-flex align-center">
            <v-col cols="7">
              <span v-if="!loading">{{ title }}</span>
              <v-skeleton-loader v-else type="heading" tile></v-skeleton-loader>
            </v-col>
            <v-col cols="5">
              <slot name="action" />
            </v-col>
          </v-row>
        </v-list-item-title>
        <v-list-item-subtitle v-if="$slots['subtitle'] || subtitle">
          <slot v-if="$slots['subtitle']" name="subtitle" />
          <span v-else class="pb-1">{{ subtitle }}</span>
        </v-list-item-subtitle>
        <v-list-item-subtitle v-if="$slots['badge']">
          <slot name="badge" />
        </v-list-item-subtitle>
      </v-list-item-content>
    </v-list-item>

    <v-divider class="ml-12 mr-2"></v-divider>
  </div>
</template>
