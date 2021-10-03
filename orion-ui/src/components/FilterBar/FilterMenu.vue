<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content d-flex align-center justify-start pa-2">
      <Button class="mr-2" height="36px" @click="toggleMenu(0)">
        <i class="pi pi-filter-3-line" />
        Run States
      </Button>

      <Button class="mr-2" height="36px" @click="toggleMenu(1)">
        <i class="pi pi-filter-3-line" />
        Timeframe
      </Button>

      <Button class="mr-2" height="36px" @click="toggleMenu(2)">
        <i class="pi pi-filter-3-line" />
        Tags
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
import { ref } from 'vue'
import RunStatesMenu from './RunStatesMenu.vue'
import TimeframeMenu from './TimeframeMenu.vue'
import TagsMenu from './TagsMenu.vue'

const menus = ref([
  {
    component: RunStatesMenu,
    show: false
  },
  {
    component: TimeframeMenu,
    show: false
  },
  {
    component: TagsMenu,
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
