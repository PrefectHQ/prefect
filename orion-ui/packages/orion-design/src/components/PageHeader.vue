<template>
  <div class="page-header" :class="classes.container">
    <template v-if="icon">
      <i class="pi page-header__icon" :class="`pi-${icon}`" />
    </template>
    <slot :heading="heading">
      <h1 class="page-header__title">
        {{ heading }}
      </h1>
    </slot>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue'
  import { Icon } from '@/types/icons'

  const props = defineProps<{
    heading?: string,
    icon?: Icon,
  }>()

  const classes = computed(() => ({
    container: {
      'page-header--with-icon':!!props.icon,
    },
  }))
</script>

<style lang="scss">
.page-header {
  margin: var(--m-2) 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) max-content;
  gap: var(--p-1);
  justify-content: space-between;
  align-items: center;
  height: 62px;
  min-width: 0;
}

.page-header--with-icon {
  grid-template-columns: minmax(0, 24px) minmax(0, 1fr) max-content;
}
</style>