<template>
  <section class="panel-section">
    <header class="panel-section__header">
      <template v-if="icon">
        <i class="pi panel-section__icon" :class="`pi-${icon}`" />
      </template>
      <div class="panel-section__heading">
        <slot name="heading">
          {{ heading }}
        </slot>
      </div>
    </header>
    <div class="panel-section__content" :class="classes.content">
      <slot />
    </div>
  </section>
</template>

<script lang="ts" setup>
  import { Icon } from '@/types/icons'
  import { computed } from 'vue';

  const props = defineProps<{
    icon?: Icon,
    heading?: string,
    full?: boolean
  }>()

  const classes = computed(() => ({
    content: {
      'panel-section__content--full': props.full
    }
  }))
</script>

<style lang="scss">
.panel-section {
  margin-left: calc(var(--panel-padding) * -1);
  margin-right: calc(var(--panel-padding) * -1);
}

.panel-section__header,
.panel-section__content {
  padding: var(--panel-padding);
}

.panel-section__content--full {
  padding: 0;
}

.panel-section__header {
  border-top: 1px solid var(--secondary-hover);
  border-bottom: 1px solid var(--secondary-hover);
  display: flex;
  align-items: center;
  gap: var(--m-1);
}

.panel-section__icon {
  color: var(--grey-40);
  position: relative;
  top: 0.05em;
}

.panel-section__heading {
  font-family: Barlow;
  font-style: normal;
  font-weight: 600;
  font-size: 18px;
  line-height: 28px;
  color: var(--grey-80);
}

</style>