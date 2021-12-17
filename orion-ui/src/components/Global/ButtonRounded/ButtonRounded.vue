<template>
  <button class="button-rounded" :class="classes">
    <slot />
  </button>
</template>

<script lang="ts">
import { Vue, Options, prop } from 'vue-class-component'

class Props {
  disabled = prop<boolean>({ default: false, type: Boolean })
}

@Options({})
export default class ButtonCard extends Vue.with(Props) {
  get classes() {
    return {
      'button-rounded--disabled': this.disabled
    }
  }
}
</script>

<style lang="scss" scoped>
.button-rounded {
  background: none;
  border-radius: 100px;
  border: 1px solid var(--blue-20);
  color: $primary;
  cursor: pointer;
  font-size: 12px;
  font-family: $font--secondary;
  height: min-content;
  padding: 2px 8px;
  user-select: none;
  white-space: nowrap;
  width: min-content;

  &::-moz-focus-inner {
    outline: none;
  }

  &:not(.button-rounded--disabled) {
    &:hover,
    &:focus,
    &:focus-visible,
    &:focus-within {
      outline: none;
      background-color: $secondary-hover;
    }

    &:active {
      background-color: $secondary-pressed;
    }
  }
}

.button-rounded--disabled {
  cursor: text;
  color: var(--grey-80);
}
</style>
