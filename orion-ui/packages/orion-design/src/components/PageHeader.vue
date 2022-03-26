<template>
  <div class="page-header">
    <div class="page-header-slot">
      <template v-if="icon">
        <i class="page-header__icon pi" :class="`pi-${icon}`" />
      </template>
      <slot :heading="heading">
        <h1 class="page-header__title">
          {{ heading }}
        </h1>
      </slot>
    </div>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { Icon } from '@/types/icons'

  defineProps<{
    heading?: string,
    icon?: Icon,
  }>()
</script>

<style lang="scss">
.page-header {
  margin: var(--m-2) 0;
  display: flex;
  gap: var(--p-1);
  align-items: center;
  flex-wrap: wrap;
  min-height: 62px;
}

.page-header__icon {
  flex-grow: 0;
}

.page-header-slot {
  display: flex;
  gap: var(--p-1);
  flex-grow: 1;
  align-items: center;
  min-width: 0;
}

.page-header__actions {
  flex-grow: 0;
  flex-shrink: 0;
}
</style>