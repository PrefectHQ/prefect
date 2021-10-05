<template>
  <Card class="menu font--primary" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-space-between align-center">
        <a
          class="
            text--primary text-decoration-none
            font--secondary
            caption
            nowrap
          "
        >
          Clear all
        </a>

        <h3 class="d-flex align-center font--secondary">
          <i class="pi pi-filter-3-line mr-1" />
          Save filters
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          flat
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content d-flex align-center justify-start pa-2">
      This is where a search menu goes
    </div>

    <template v-slot:actions>
      <CardActions class="pa-2 menu-actions d-flex align-center justify-end">
        <Button
          v-if="!smAndDown"
          flat
          height="35px"
          class="ml-auto mr-1"
          @click="close"
        >
          Cancel
        </Button>
        <Button
          color="primary"
          height="35px"
          :width="smAndDown ? '100%' : 'auto'"
          @click="save"
        >
          Save
        </Button>
      </CardActions>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { reactive, computed, defineEmits, watch, getCurrentInstance } from 'vue'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])

const close = () => {
  emit('close')
}

const save = () => {
  console.log('save')
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
    border-top: 1px solid $secondary-hover;
    border-radius: 0 !important;
    background-color: $grey-10;
    overscroll-behavior: contain;
    height: 100%;
    overflow: auto;

    @media (max-width: 640px) {
      width: 100%;
    }
  }

  .menu-actions {
    border-top: 1px solid $secondary-hover;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
    max-height: inherit;
  }

  .menu-container {
    position: relative;
  }
}
</style>
