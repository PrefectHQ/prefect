<template>
  <Card class="menu font--primary" tabindex="0">
    <div class="menu-content pa-2">
      <div class="d-flex align-center justify-start">
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

      <div v-if="filters.length" class="mt-2 d-flex align-center justify-start">
        <FilterTag
          v-for="(filter, i) in filters"
          :key="i"
          :item="filter"
          class="mr--half"
          @click="handleTagClick(filter)"
          @remove="removeFilter"
        />
      </div>
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
import {
  ref,
  reactive,
  shallowRef,
  computed,
  ComponentPublicInstance
} from 'vue'
import { useStore } from 'vuex'
import RunStatesMenu from './RunStatesMenu.vue'
import TimeframeMenu from './TimeframeMenu.vue'
import TagsMenu from './TagsMenu.vue'
import ObjectMenu from './ObjectMenu.vue'
import FilterTag from './FilterTag.vue'
import { parseFilters, FilterObject } from './util'

const store = useStore()
const selectedObject = ref('flow_runs')

const menuRefs = ref<ComponentPublicInstance[]>([])

const iconMap: { [key: string]: string } = {
  flow_runs: 'pi-flow-run',
  task_runs: 'pi-task',
  flows: 'pi-flow',
  deployments: 'pi-map-pin-line'
}

// TODO: This is really hacky so we probably want to refactor sooner rather than later.
const menus = reactive([
  {
    key: 'object',
    label: computed(() => selectedObject.value.replace('_', ' ')),
    component: shallowRef(ObjectMenu),
    icon: computed(() => iconMap[selectedObject.value]),
    show: false,
    objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
  },
  {
    key: 'states',
    label: 'Run States',
    component: shallowRef(RunStatesMenu),
    show: false,
    objects: ['flow_runs', 'task_runs']
  },
  {
    key: 'timeframe',
    label: 'Timeframe',
    component: shallowRef(TimeframeMenu),
    show: false,
    objects: ['flow_runs', 'task_runs']
  },
  {
    key: 'tags',
    label: 'Tags',
    component: shallowRef(TagsMenu),
    show: false,
    objects: ['flow_runs', 'task_runs', 'flows', 'deployments']
  }
])

const removeFilter = (filter: FilterObject): void => {
  console.log(filter)
}

const handleTagClick = (tag: FilterObject) => {
  const menu = menus.findIndex((m) => m.key == tag.filterKey)

  if (menu > -1) {
    closeAllMenus()
    menus[menu].show = true
  }
}

const filters = computed<FilterObject[]>(() => {
  return parseFilters({
    [selectedObject.value]: store.getters.globalFilter[selectedObject.value]
  })
})

const menuButtons = computed(() => {
  return menus.filter((m) => m.objects.includes(selectedObject.value))
})

const elRef = (el: ComponentPublicInstance, i: number) => {
  if (el) menuRefs.value[i] = el
}

const subMenuStyle = computed(() => {
  const index = menus.findIndex((m) => m.show)
  const bb = menuRefs.value[index].$el
  return {
    top: bb.offsetHeight + bb.offsetHeight / 2 + 2 + 'px',
    left: bb.offsetLeft + 'px'
  }
})

const closeAllMenus = () => {
  menus.forEach((m) => (m.show = false))
}

const toggleMenu = (i: number) => {
  menus.filter((m, j) => j !== i).forEach((m) => (m.show = false))
  menus[i].show = !menus[i].show
}
</script>

<style lang="scss" scoped>
@use '@/styles/components/global-filter--filter-menu.scss';
</style>
