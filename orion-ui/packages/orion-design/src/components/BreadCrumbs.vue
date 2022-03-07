<template>
  <component :is="tag" class="bread-crumbs">
    <i v-if="icon" class="pi text--grey-40 mr-2" :class="icon" />
    <span class="bread-crumbs__crumbs">
      <span
        v-for="(crumb, index) in crumbs"
        :key="index"
        class="bread-crumbs__crumb"
        :class="{
          'bread-crumbs__crumb--bold': bold && index === crumbs.length - 1,
        }"
      >
        <BreadCrumb :crumb="crumb" />
      </span>
    </span>
  </component>
</template>

<script lang="ts" setup>
  import { withDefaults } from 'vue'
  import BreadCrumb from '@/components/BreadCrumb.vue'
  import { Crumb } from '@/models/Crumb'

  interface Props {
    crumbs: Crumb[],
    icon?: string | null,
    tag?: string,
    bold?: boolean,
  }

  withDefaults(defineProps<Props>(), {
    tag: 'h1',
    icon: null,
  })
</script>

<style lang="scss">
.bread-crumbs__crumb {
  font-size: 14px;

  &:last-child {
    display: block;
    font-size: 20px;
    margin: -6px 0 2px;
  }

  &:not(:nth-last-child(-n + 2))::after {
    content: '\00a0/\00a0';
  }
}

.bread-crumbs__crumb--bold {
  font-weight: 600;
}

@media (min-width: 640px) {
  .bread-crumbs__crumb {
    font-size: 20px;

    &:last-child {
      display: inline;
      margin: 0;
    }

    &:not(:last-child)::after {
      content: '\00a0/\00a0';
    }
  }
}
</style>
