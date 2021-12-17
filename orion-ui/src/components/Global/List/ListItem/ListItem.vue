<template>
  <li class="list-item">
    <template v-if="icon">
      <i class="pi list-item__icon" :class="icon" />
    </template>
    <slot />
  </li>
</template>

<script lang="ts">
import { prop, Vue } from 'vue-class-component'

class Props {
  icon = prop<string>({ default: null })
}

export default class ListItem extends Vue.with(Props) {}
</script>

<style lang="scss">
.list-item {
  background-color: $white;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 9px 16px;
  width: 100%;

  &:first-of-type {
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
  }

  &:not(:first-of-type) {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;

    border-top: 1px solid $secondary-hover;
  }

  &:last-of-type {
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
  }
}

.list-item__icon {
  margin-top: 0.1em;
  color: var(--grey-40);
  align-self: flex-start;
  margin-right: var(--m-2);
}

.list-item__title {
  flex: 1;
  min-width: 0;

  > * {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
