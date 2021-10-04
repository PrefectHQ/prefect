<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content d-flex align-center justify-start pa-2">
      <Button
        v-for="(menu, i) in menuButtons"
        :key="i"
        class="mr-2"
        height="36px"
        :ref="(el) => elRef(el, i)"
        @click="toggleMenu(i)"
      >
        <i class="pi" :class="menu.icon ? menu.icon : 'pi-filter-3-line'" />
        <span class="text-capitalize ml-1">{{ menu.label }}</span>
      </Button>
    </div>

    <component
      v-for="(menu, i) in menus.filter((m) => m.show)"
      :key="i"
      :is="menu.component"
      v-model="selectedObject"
      class="sub-menu"
      :object="selectedObject"
      :style="subMenuStyle"
      @close="menu.show = false"
    />
  </Card>
</template>

<script lang="ts" setup>
import { ref, shallowRef, computed, ComponentPublicInstance } from 'vue'
import RunStatesMenu from './RunStatesMenu.vue'
import TimeframeMenu from './TimeframeMenu.vue'
import TagsMenu from './TagsMenu.vue'
import ObjectMenu from './ObjectMenu.vue'

const selectedObject = ref('flow_runs')

const menuRefs = ref<ComponentPublicInstance[]>([])

// TODO: This is really hacky so we probably want to refactor sooner rather than later.
const menus = ref([
  {
    label: selectedObject.value.replace('_', ' '),
    component: shallowRef(ObjectMenu),
    icon: `pi-${selectedObject.value
      .replace('_', '-')
      .slice(0, selectedObject.value.length - 1)}`,
    value: selectedObject.value,
    show: false,
    objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
  },
  {
    label: 'Run States',
    component: shallowRef(RunStatesMenu),
    show: false,
    objects: ['flow_runs', 'task_runs']
  },
  {
    label: 'Timeframe',
    component: shallowRef(TimeframeMenu),
    show: false,
    objects: ['flow_runs', 'task_runs']
  },
  {
    label: 'Tags',
    component: shallowRef(TagsMenu),
    show: false,
    objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
  }
])

const menuButtons = computed(() => {
  return menus.value.filter((m) => m.objects.includes(selectedObject.value))
})

const elRef = (el: ComponentPublicInstance, i: number) => {
  if (el) menuRefs.value[i] = el
}

const subMenuStyle = computed(() => {
  const index = menus.value.findIndex((m) => m.show)
  const bb = menuRefs.value[index].$el
  return {
    top: bb.offsetHeight + bb.offsetHeight / 2 + 2 + 'px',
    left: bb.offsetLeft + 'px'
  }
})

const toggleMenu = (i: number) => {
  menus.value.filter((m, j) => j !== i).forEach((m) => (m.show = false))
  menus.value[i].show = !menus.value[i].show
}
</script>

<style lang="scss" scoped>
.menu {
  border-radius: 0;
  position: relative;

  .sub-menu {
    position: absolute;
  }

  .menu-content {
    border-top: 2px solid $grey-10;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
  }

  .menu-container {
    position: relative;
  }
}

.object {
  text-transform: capitalize;
}

.object-container,
.saved-searches-container {
  position: relative;

  .object-menu {
    position: absolute;
    top: 100%;
    left: 0;
    z-index: 2;
  }
}

.filter-button {
  align-items: center;
  background-color: $white;
  border: none;
  cursor: pointer;
  display: flex;
  height: 100%;
  min-width: 52px;
  outline: none;

  &:hover,
  &:focus {
    background-color: $grey-10;
  }

  &:active {
    background-color: $grey-20;
  }

  $border-style: 2px solid $grey-10;

  &.objects {
    border-right: $border-style;
    border-radius: 4px 0 0 4px;
  }
}
</style>
