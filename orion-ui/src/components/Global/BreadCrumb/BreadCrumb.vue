<template>
  <h2>
    <i class="pi" :class="props.icon" />
    <span
      v-skeleton="!crumb.text"
      v-for="crumb in props.crumbs"
      :key="crumb.text"
      style="min-width: 100px"
    >
      {{ crumb.text }}
    </span>
  </h2>
</template>

<script lang="ts" setup>
import { defineProps } from 'vue'

type Crumb = {
  text: string
  route?: string
}

const props = defineProps<{ crumbs: Crumb[]; icon: string }>()
</script>
