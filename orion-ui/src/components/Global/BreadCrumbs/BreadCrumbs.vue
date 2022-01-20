<template>
  <component :is="props.tag" class="bread-crumbs">
    <i v-if="props.icon" class="pi text--grey-40 mr-2" :class="props.icon" />
    <div class="bread-crumbs__crumbs">
      <div class="bread-crumbs__crumbs--first">
        <template v-for="crumb in firstCrumbs" :key="crumb.text">
          <BreadCrumb :crumb="crumb" />
        </template>
      </div>
      <div class="bread-crumbs__crumbs--last">
        <component :is="boldTag">
          <BreadCrumb :crumb="lastCrumb" />
        </component>
      </div>
    </div>
  </component>
</template>

<script lang="ts" setup>
import { withDefaults, computed } from 'vue'
import { Crumb } from '../utils'
import BreadCrumb from '@/components/Global/BreadCrumb/BreadCrumb.vue'

interface Props {
  crumbs: Crumb[]
  icon?: string
  tag?: string
  bold?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'h1',
  bold: false
})

const firstCrumbs = computed(() => {
  return props.crumbs.slice(0, props.crumbs.length - 1)
})

const lastCrumb = computed(() => {
  return props.crumbs.slice(-1)[0]
})

const boldTag = computed(() => {
  return props.bold ? 'strong' : 'span'
})
</script>

<style lang="scss" scoped>
.bread-crumbs {
  &__crumbs {
    &--first {
      font-size: 14px;
    }

    &--last {
      font-size: 20px;
      margin: -6px 0 2px;
    }

    @media (min-width: 640px) {
      display: flex;

      &--first {
        font-size: 20px;
      }

      &--last {
        font-size: 20px;
        margin: 0;
      }

      &--first::after {
        content: '\00a0/\00a0';
      }
    }
  }
}
</style>
