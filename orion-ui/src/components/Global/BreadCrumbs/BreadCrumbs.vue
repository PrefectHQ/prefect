<template>
  <div class="bread-crumbs">
    <i v-if="icon" class="pi text--grey-40 mr-2" :class="props.icon" />
    <div class="bread-crumbs__first">
      <BreadCrumb :crumbs="firstCrumbs" :slash="true" :tag="tagSizeOption" />
    </div>
    <div class="bread-crumbs__last">
      <BreadCrumb :crumbs="lastCrumb" :tag="props.tag" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { withDefaults, computed } from 'vue'
import BreadCrumb from '@/components/Global/BreadCrumb/BreadCrumb.vue'

type Crumb = {
  text: string
  to?: string
}

interface Props {
  crumbs: Crumb[]
  icon?: string
  tag?: string
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'h1'
})

const firstCrumbs = computed(() => {
  return props.crumbs.slice(0, props.crumbs.length - 1)
})

const lastCrumb = computed(() => {
  return props.crumbs.slice(-1)
})

const tagSizeOption = computed(() => {
  return window.innerWidth < 640 ? 'span' : props.tag
})
</script>

<style lang="scss" scoped>
@use 'sass:map';

.bread-crumbs {
  min-height: 30px;
  display: flex;
  align-items: center;
}

@media (max-width: 640px) {
  .bread-crumbs {
    display: flex;
    justify-content: center;
    align-items: baseline;
    flex-direction: column;

    &__first {
      font-size: 14px !important;
    }

    &__last {
      margin: -6px 0 2px;
    }
  }
}
</style>
