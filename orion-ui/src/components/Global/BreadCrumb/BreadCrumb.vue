<template>
  <component
    :is="props.tag || 'h1'"
    class="d-flex align-center"
    style="max-width: 100%"
  >
    <i v-if="icon" class="pi text--grey-40 mr-2" :class="props.icon" />
    <span
      v-skeleton="!crumb.text"
      v-for="(crumb, i) in props.crumbs"
      :key="crumb.text"
      :style="{
        minWidth: !crumb.text ? '40px' : undefined,
        maxWidth: '50%',
        minHeight: '30px'
      }"
      class="text-truncate"
    >
      <component
        :is="crumb.to ? 'router-link' : 'span'"
        :to="crumb.to"
        class="text-truncate"
        :class="{ 'font-weight-semibold': i == props.crumbs.length - 1 }"
      >
        {{ crumb.text }}
      </component>
      {{ i !== props.crumbs.length - 1 ? '&nbsp;/&nbsp;' : '' }}
    </span>
  </component>
</template>

<script lang="ts" setup>
import { defineProps } from 'vue'

type Crumb = {
  text: string
  to?: string
}

const props = defineProps<{ crumbs: Crumb[]; icon: string; tag: 'string' }>()
</script>
