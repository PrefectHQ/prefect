<template>
  <component :is="tabSetType" class="list-tab-set" :tabs="tabs">
    <template #after-tab="{ tab }">
      <template v-if="tab.count !== null">
        <span class="list-tab-set__tab-count">{{ tab.count.toLocaleString() }}</span>
      </template>
    </template>

    <template #before-tab-content="{ selectedTab }">
      <div class="list-tab-set__list-count">
        <template v-if="selectedTab.count !== null">
          <span>{{ selectedTab.count.toLocaleString() }} {{ toPluralString('Result', selectedTab.count) }}</span>
        </template>
      </div>
    </template>

    <template v-for="(index, name) in $slots" #[name]="data">
      <slot :name="name" v-bind="data" />
    </template>
  </component>
</template>

<script lang="ts" setup>
  import { computed, PropType } from 'vue'
  import RouterTabSet from '@/components/RouterTabSet.vue'
  import TabSet from '@/components/TabSet.vue'
  import { isRouterTab, ListRouterTab, ListTab } from '@/types/tabs'
  import { toPluralString } from '@/utilities/strings'

  const props = defineProps({
    tabs: {
      type: Array as PropType<Readonly<(ListTab[] | ListRouterTab[])>>,
      required: true,
      validator:(value: Readonly<(ListTab[] | ListRouterTab[])>) => value.length > 0,
    },
  })

  const tabSetType = computed(() => props.tabs.every(isRouterTab) ? RouterTabSet : TabSet)
</script>

<style lang="scss">
.list-tab-set__tab-count {
    background-color: var(--white);
    border-radius: 16px;
    font-weight: 400;
    padding: 0 var(--p-1);
    min-width: 24px;
    font-size: 13px;
    transition: 150ms all;
  }

  .tab-set__tab--active {
      background-color: var(--primary);
      color: var(--white);

      .list-tab-set__tab-count {
          background-color: var(--primary);
          color: var(--white);
      }
  }

  .list-tab-set__list-count {
    font-size: 13px;
    letter-spacing: -.09px;
    line-height: 18px;
    min-height: 17px;
    font-family: "input-sans";
    margin: var(--m-2) 0;
  }
</style>