<template>
  <div class="bread-crumbs">
    <template v-if="icon">
      <div class="bread-crumbs__icon">
        <i class="pi" :class="`pi-${icon}`" />
      </div>
    </template>

    <div class="bread-crumbs__crumbs">
      <template v-for="(crumb, index) in crumbs" :key="index">
        <component
          :is="!isLast(index) && stacked ? 'span' : tag"
          class="bread-crumbs__crumb"
          :class="classes.crumb(index)"
        >
          <BreadCrumb :crumb="crumb" />
        </component>
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, withDefaults } from 'vue'
  import BreadCrumb from '@/components/BreadCrumb.vue'
  import { Crumb } from '@/models/Crumb'
  import { Icon } from '@/types/icons'

  const props = withDefaults(defineProps<{
    crumbs: Crumb[],
    tag?: string,
    stacked?: boolean,
    icon?: Icon,
  }>(), {
    tag: 'h1',
    icon: undefined,
  })

  const classes = computed(() => ({
    crumb:(index: number) => ({
      'bread-crumbs__crumb--block': props.stacked && isLast(index),
      'bread-crumbs__crumb--inline': !props.stacked || !isLast(index),
      'bread-crumbs__crumb--separate': hasSeparator(index),
    }),
  }))

  function hasSeparator(index: number): boolean {
    let lastIndex = props.crumbs.length - 1

    if (props.stacked) {
      lastIndex--
    }

    return index < lastIndex
  }

  function isLast(index: number): boolean {
    return index === props.crumbs.length - 1
  }
</script>

<style lang="scss">
.bread-crumbs {
  display: flex;
  align-items: center;
}

.bread-crumbs__icon {
  display: flex;
  align-items: center;
  color: var(--grey-40);
  margin-right: var(--m-1);
}

.bread-crumbs__crumb {
  vertical-align: baseline;
}

.bread-crumbs__crumb--inline {
  display: inline-block;
}

.bread-crumbs__crumb--block {
  display: block;
}

.bread-crumbs__crumb--separate > :after {
  color: var(--grey-80);
  content: '\00a0/\00a0';
}
</style>
