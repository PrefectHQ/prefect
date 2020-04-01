<script>
export default {
  props: {
    clickable: {
      type: Boolean,
      default: false,
      required: false
    },
    outlined: {
      type: Boolean,
      default: true,
      required: false
    }
  },
  methods: {
    handleClick() {
      this.$emit('click', this.$slots.default[0].text)
    }
  }
}
</script>

<template>
  <v-chip
    :disabled="!clickable"
    color="primary"
    :outlined="outlined"
    small
    style="user-select: auto;"
    @click="handleClick"
  >
    <slot></slot>
  </v-chip>
</template>

<style lang="scss" scoped>
.v-chip--disabled {
  opacity: 1;
}
</style>
