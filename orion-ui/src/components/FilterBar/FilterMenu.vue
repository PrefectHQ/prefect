<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content d-flex align-center justify-start pa-2">
      <Button
        v-for="(menu, i) in menus"
        :key="i"
        class="mr-2"
        height="36px"
        @click="toggleMenu(i)"
      >
        <i class="pi pi-filter-3-line" />
        {{ menu.label }}
      </Button>
    </div>

    <!-- TODO: Put these in actual overflow menus -->
    <div>
      <component
        v-for="(menu, i) in menus.filter((m) => m.show)"
        :key="i"
        :is="menu.component"
        @close="toggleMenu(i)"
      />
    </div>
  </Card>
</template>

<script lang="ts" setup>
import { ref, shallowRef } from 'vue'
import RunStatesMenu from './RunStatesMenu.vue'
import TimeframeMenu from './TimeframeMenu.vue'
import TagsMenu from './TagsMenu.vue'

const menus = ref([
  {
    label: 'Run States',
    component: shallowRef(RunStatesMenu),
    show: false
  },
  {
    label: 'Timeframe',
    component: shallowRef(TimeframeMenu),
    show: false
  },
  {
    label: 'Tags',
    component: shallowRef(TagsMenu),
    show: false
  }
])

const toggleMenu = (i: number) => {
  menus.value[i].show = !menus.value[i].show
}
</script>

<style lang="scss" scoped>
.menu {
  width: 100%;
  border-radius: 0;

  .menu-content {
    border-top: 2px solid $grey-10;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
  }

  .menu-container {
    position: relative;

    .sub-menu {
      position: absolute;
      left: 0;
      top: 0;
      z-index: 1;
    }
  }
}
</style>
