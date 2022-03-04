<template>
  <!-- todo: have this expect breadcrumbs when that component is done -->
  <div class="page-header">
    <h1 class="page-header__title">
      <i class="pi page-header__icon" :class="`pi-${icon}`" />
      <slot />
    </h1>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { PropType } from 'vue'
  import { Icon } from '@/types/icons'

  defineProps({
    icon: {
      type: String as PropType<Icon>,
      required: false,
      default: null,
    },
  })
</script>

<style lang="scss">
.page-header {
  margin: var(--m-2) 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 62px;
}

.page-header__icon {
  position: relative;
  top: 0.1em;
  color: var(--grey-40);
  margin-right: var(--m-1);
}
</style>