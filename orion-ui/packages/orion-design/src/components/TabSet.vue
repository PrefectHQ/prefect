<template>
  <div class="tab-set">
    <m-tabs v-model="internalSelectedTabKey">
      <m-tab
        v-for="tab in tabs"
        :key="tab.key"
        :href="tab.key"
        class="tab-set__tab"
        :class="classes.tab(tab)"
      >
        <i class="pi" :class="tab.icon" />
        <span class="tab-set__tab-title">{{ tab.title }}</span>
        <slot name="after-tab" :tab="tab" />
      </m-tab>
    </m-tabs>

    <div class="tab-set__results">
      <transition-group name="tab-fade" mode="out-in" css>
        <span key="before-tab-content">
          <slot name="before-tab-content" :selected-tab="selectedTab" />
        </span>
        <span v-for="tab in tabs" :key="tab.key">
          <slot v-if="isSelected(tab)" :name="tab.key" :tab="tab" />
        </span>
        <span key="after-tab-content">
          <slot name="after-tab-content" :selected-tab="selectedTab" />
        </span>
      </transition-group>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, PropType } from 'vue'
  import { Tab } from '@/types/tabs'

  const props = defineProps({
    tabs: {
      type: Array as PropType<Readonly<Tab[]>>,
      required: true,
      validator:(value: Tab[]) => value.length > 0,
    },
    value: {
      type: String,
      default: null,
    },
  })

  const emit = defineEmits<{
    (event: 'update:value', value: string): void,
  }>()

  const classes = computed(() => ({
    tab: (tab: Tab) => [
      tab.class,
      { 'tab-set__tab--active': isSelected(tab) },
    ],
  }))

  const isSelected = (tab: Tab): boolean => {
    return tab.key === selectedTab.value.key
  }

  const getTabByKey = (key: string | undefined): Tab => {
    const [defaultTab] = props.tabs
    if (!key) {
      return defaultTab
    }

    return props.tabs.find(tab => tab.key === key) ?? defaultTab
  }

  const selectedTab = computed<Tab>(() => {
    return getTabByKey(props.value)
  })

  const internalSelectedTabKey = computed<string>({
    get: () => selectedTab.value.key,
    set: value => emit('update:value', value),
  })
</script>

<style lang="scss">
.tab-set {
    margin: 40px auto;
}

.tab-set__tab--active {
    background-color: var(--primary);
    color: #fff;
}

.tab-set__tab-title {
    margin: 0 8px;
}

.tab-fade-enter-active,
.tab-fade-leave-active {
    opacity: 0;
    transition: opacity 150ms ease;
}
</style>