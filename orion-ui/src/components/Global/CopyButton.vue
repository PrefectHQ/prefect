<template>
  <button class="copy-button" @click="copy">
    <i class="pi pi-file-copy-line pi-sm" />
    <span class="copy-button__label">
      <slot>Copy</slot>
    </span>
  </button>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue'

export default defineComponent({
  props: {
    value: {
      type: String as PropType<string>,
      required: true
    },
    toast: {
      type: String as PropType<string>,
      default: 'Copied to Clipboard'
    }
  },
  methods: {
    copy() {
      navigator.clipboard.writeText(this.value)

      this.$toast({
        type: 'success',
        message: this.toast
      })
    }
  }
})
</script>

<style lang="scss" scoped>
.copy-button {
  display: inline-flex;
  align-items: center;
  background: transparent;
  border: none;
  color: $primary;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  text-decoration: none;
  transition: all 50ms;
  user-select: none;

  &:hover,
  &:focus {
    & .copy-button__label {
      text-decoration: underline;
    }
  }

  &:active {
    background: transparent;
    color: $primary-hover;
  }
}

.copy-button__label {
  margin-left: 4px;
}
</style>
