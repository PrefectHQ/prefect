<template>
  <component :is="props.tag || 'h1'">
    <span
      v-skeleton="!crumb.text"
      v-for="(crumb, i) in props.crumbs"
      :key="crumb.text"
    >
      <component
        :is="crumb.to ? 'router-link' : 'span'"
        :to="crumb.to"
        class="text-truncate"
      >
        {{ crumb.text }}
      </component>
      {{ props.slash && !smallScreenWidth ? '&nbsp;/&nbsp;' : '' }}
      {{
        props.slash && smallScreenWidth && i !== props.crumbs.length - 1
          ? '&nbsp;/&nbsp;'
          : ''
      }}
    </span>
  </component>
</template>

<script lang="ts" setup>
import { computed, withDefaults } from 'vue'

type Crumb = {
  text: string
  to?: string
}

interface Props {
  crumbs: Crumb[]
  tag?: string
  slash?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'h1'
})

const smallScreenWidth = computed<boolean>(() => {
  return window.innerWidth < 640
})
</script>

<style lang="scss" scoped>
a {
  text-decoration: none;

  &:hover {
    color: $primary !important;
    text-decoration: underline;
  }

  &:active {
    color: $primary-hover !important;
  }
}
</style>
