<template>
  <Card class="menu font--primary" height="100%" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <h3 class="d-flex align-center font--secondary ml-auto">
          <i class="pi pi-star-line mr-1" />
          Save search
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          class="ml-auto"
          flat
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content d-flex align-center justify-start pa-2">
      This is where a save search menu goes
    </div>
  </Card>
</template>

<script lang="ts" setup>
import { reactive, computed, defineEmits, watch, getCurrentInstance } from 'vue'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])

const close = () => {
  emit('close')
}

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
})
</script>

<style lang="scss" scoped>
.menu {
  border-radius: 0;
  position: relative;

  .menu-content {
    border-top: 2px solid $grey-10;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
  }
}
</style>
