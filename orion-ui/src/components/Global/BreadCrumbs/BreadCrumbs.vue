<template>
  <component :is="props.tag || 'h1'" class="d-flex align-center">
    <i v-if="props.icon" class="pi text--grey-40 mr-2" :class="props.icon" />
    <div class="bread-crumbs">
      <div class="bread-crumbs__first">
        <template v-for="(crumb, i) in firstCrumbs" :key="crumb.text">
          <BreadCrumb :crumb="crumb" />
          {{ i !== firstCrumbs.length - 1 ? '&nbsp;/&nbsp;' : '' }}
        </template>
      </div>
      <div class="bread-crumbs__last">
        <BreadCrumb :crumb="lastCrumb" />
      </div>
    </div>
  </component>
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
  return props.crumbs.slice(-1)[0]
})
</script>

<style lang="scss" scoped>
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
