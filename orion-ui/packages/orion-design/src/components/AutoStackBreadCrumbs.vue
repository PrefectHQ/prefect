<template>
  <OverflowWrapper>
    <template #default="{ overflows }">
      <BreadCrumbs :stacked="overflows" :crumbs="crumbs" :tag="tag" :icon="icon" />
    </template>
  </OverflowWrapper>
</template>

<script lang="ts" setup>
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import OverflowWrapper from '@/components/OverflowWrapper.vue'
  import { Crumb } from '@/models/Crumb'
  import { Icon } from '@/types/icons'

  defineProps<{ crumbs: Crumb[], tag?: string, icon?: Icon }>()
</script>