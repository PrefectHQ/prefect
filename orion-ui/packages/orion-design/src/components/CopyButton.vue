<template>
  <button class="copy-button" @click="copy">
    <i class="pi pi-file-copy-line pi-sm" />
    <template v-if="label == null || $slots.default">
      <span class="copy-button__label">
        <slot>{{ labelOrDefault }}</slot>
      </span>
    </template>
  </button>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue'

export default defineComponent({
  props: {
    value: {
      type: [String, Function] as PropType<string | (() => string)>,
      required: true
    },
    label: {
      type: String,
      default: null
    },
    toast: {
      type: String,
      default: 'Copied to Clipboard'
    },
    timeout: {
      type: Number,
      default: 5000
    }
  },
  computed: {
    labelOrDefault() {
      return this.label ?? 'Copy'
    }
  },
  methods: {
    copy() {
      if (typeof this.value === 'function') {
        navigator.clipboard.writeText(this.value())
      } else {
        navigator.clipboard.writeText(this.value)
      }

      this.$toast({
        type: 'success',
        message: this.toast,
        timeout: this.timeout
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
  font-family: var(--font-primary);

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
