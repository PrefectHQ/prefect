<template>
  <h1 class="d-flex align-center">
    <i class="pi text--grey-40 mr-2" :class="props.icon" />
    <span
      v-skeleton="!crumb.text"
      v-for="(crumb, i) in props.crumbs"
      :key="crumb.text"
      :style="{ minWidth: !crumb.text ? '40px' : undefined }"
      :class="{ 'font-weight-semibold': i == props.crumbs.length - 1 }"
    >
      {{ crumb.text }}{{ i !== props.crumbs.length - 1 ? '&nbsp;/&nbsp;' : '' }}
    </span>
  </h1>
</template>

<script lang="ts" setup>
import { defineProps } from 'vue'

type Crumb = {
  text: string
  route?: string
}

const props = defineProps<{ crumbs: Crumb[]; icon: string }>()
</script>
