<template>
  <component :is="props.tag" class="bread-crumbs">
    <i v-if="props.icon" class="pi text--grey-40 mr-2" :class="props.icon" />
    <div class="bread-crumbs__crumbs">
      <div class="bread-crumbs__crumbs--first">
        <template v-for="crumb in firstCrumbs" :key="crumb.text">
          <BreadCrumb :crumb="crumb" />
        </template>
      </div>
      <span v-breakpoints="'sm'">&nbsp;/&nbsp;</span>
      <div class="bread-crumbs__crumbs--last">
        <BreadCrumb :crumb="lastCrumb" />
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
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'h1'
})

const firstCrumbs = computed(() => {
  return props.crumbs.slice(0, props.crumbs.length - 1)
})

const lastCrumb = computed(() => {
  return props.crumbs.slice(-1)[0]
})
</script>

<style lang="scss" scoped>
.bread-crumbs {
  display: flex;
  align-items: center;

  &__crumbs {
    min-height: 30px;
    display: flex;
    align-items: center;
  }
}

@media (max-width: 640px) {
  .bread-crumbs {
    &__crumbs {
      display: flex;
      justify-content: center;
      align-items: baseline;
      flex-direction: column;

      &--first {
        font-size: 14px !important;
      }

      &--last {
        margin: -6px 0 2px;
      }
    }
  }
}
</style>
