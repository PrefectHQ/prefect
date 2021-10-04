<template>
  <Card class="menu font--primary" tabindex="0">
    <template v-if="smAndDown" v-slot:header>
      <div class="pa-2 d-flex justify-space-between align-center">
        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          flat
          style="border-radius: 50%"
          @click="close"
        />

        <h3 class="d-flex align-center font--secondary">
          <i class="pi pi-filter-3-line mr-1" />
          Filters
        </h3>

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
      </div>
    </template>

    <div class="pa-2">
      <!-- <div class="d-flex align-center flex-grow-1 justify-start"> -->
      <FilterAccordion title="Deployments" icon="pi-filter-3-line">
        <div v-for="n in 5" :key="n"> TEST TEST TEST </div>
      </FilterAccordion>
      <FilterAccordion title="Flows" icon="pi-filter-3-line">
        <div v-for="n in 5" :key="n"> TEST TEST TEST </div>
      </FilterAccordion>
      <FilterAccordion title="Flow Runs" icon="pi-filter-3-line">
        <div v-for="n in 5" :key="n"> TEST TEST TEST </div>
      </FilterAccordion>
      <FilterAccordion title="Task Runs" icon="pi-filter-3-line">
        <div v-for="n in 5" :key="n"> TEST TEST TEST </div>
      </FilterAccordion>
      <!-- <Button
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
          @click.self="handleTagClick(filter)"
          @remove="removeFilter"
        /> -->
      <!-- </div> -->
    </div>

    <template v-slot:actions>
      <CardActions class="pa-2 d-flex align-center justify-end">
        <Button v-if="!smAndDown" flat height="35px" class="ml-auto mr-1">
          Cancel
        </Button>
        <Button
          color="primary"
          height="35px"
          :width="smAndDown ? '100%' : 'auto'"
        >
          Apply
        </Button>
      </CardActions>
    </template>

    <!-- <component
      v-for="(menu, i) in menus.filter((m) => m.show)"
      :key="i"
      :is="menu.component"
      v-model="selectedObject"
      class="sub-menu"
      :object="selectedObject"
      :style="subMenuStyle"
      @close="menu.show = false"
    /> -->
  </Card>
</template>

<script lang="ts" setup>
import {
  ref,
  reactive,
  shallowRef,
  computed,
  ComponentPublicInstance,
  defineEmits
} from 'vue'
import { useStore } from 'vuex'
import RunStatesMenu from './RunStatesMenu.vue'
import TimeframeMenu from './TimeframeMenu.vue'
import TagsMenu from './TagsMenu.vue'
import ObjectMenu from './ObjectMenu.vue'
import FilterTag from './FilterTag.vue'
import { parseFilters, FilterObject } from './util'
import { getCurrentInstance } from 'vue'
import FilterAccordion from './FilterAccordion.vue'

const instance = getCurrentInstance()
const emit = defineEmits(['close'])
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
  console.log('remove', filter)
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

const smAndDown = computed(() => {
  const breakpoints = instance?.appContext.config.globalProperties.$breakpoints
  return !breakpoints.md
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

const close = () => {
  emit('close')
}

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
