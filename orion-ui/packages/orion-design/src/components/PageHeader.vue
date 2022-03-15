<template>
  <div class="page-header">
    <template v-if="crumbs">
      <OverflowWrapper>
        <template #default="{ overflown }">
          <BreadCrumbs :icon="icon" :crumbs="crumbs" class="page-header__bread-crumbs" :stacked="overflown" />
        </template>
      </OverflowWrapper>
    </template>
    <template v-else>
      <h1 class="page-header__title">
        <slot />
      </h1>
    </template>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import BreadCrumbs from '@/components/BreadCrumbs.vue'
  import OverflowWrapper from '@/components/OverflowWrapper.vue'
  import { Crumb } from '@/models/Crumb'
  import { Icon } from '@/types/icons'

  defineProps<{
    icon?: Icon,
    crumbs?: Crumb[],
  }>()
</script>

<style lang="scss">
.page-header {
  margin: var(--m-2) 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 62px;
}
</style>