<template>
  <m-tabs
    class="results-list-tabs"
    :model-value="internalTab"
    @update:model-value="setTab"
  >
    <template v-for="tab in tabs" :key="tab.href">
      <m-tab
        :href="tab.href"
        :class="getTabClasses(tab)"
        @click="setTab(tab.href)"
      >
        <i class="pi results-list-tabs__icon" :class="getTabIconClasses(tab)" />
        <span class="results-list-tabs__label">{{ tab.label }}</span>
        <template v-if="getTabHasCount(tab)">
          <span
            class="results-list-tabs__badge"
            :class="getTabCountClasses(tab)"
          >
            {{ tab.count.toLocaleString() }}
          </span>
        </template>
      </m-tab>
    </template>
  </m-tabs>
</template>

<script lang="ts">
  import { defineComponent, PropType } from 'vue'
  import {
    ResultsListTab,
    ResultsListTabWithCount
  } from '../types/ResultsListTab'

  export default defineComponent({
    name: 'ResultsListTabs',
    expose: [],
    props: {
      tab: {
        type: String,
        required: true,
      },

      tabs: {
        type: Array as PropType<(ResultsListTab | ResultsListTabWithCount)[]>,
        required: true,
      },
    },

    emits: ['update:tab'],

    data(): { internalTab: string } {
      return {
        internalTab: '',
      }
    },

    watch: {
      tab: {
        immediate: true,
        handler: function(tab) {
          this.internalTab = tab
        },
      },
    },

    methods: {
      setTab(href: string) {
        this.internalTab = href
        this.$emit('update:tab', href)
      },

      getTabClasses(tab: ResultsListTab) {
        return {
          active: this.isActiveTab(tab),
        }
      },

      getTabIconClasses(tab: ResultsListTab) {
        return [
          tab.icon,
          {
            'results-list-tabs__icon--active': this.isActiveTab(tab),
          },
        ]
      },

      getTabCountClasses(tab: ResultsListTab) {
        return {
          'results-list-tabs__badge--active': this.isActiveTab(tab),
        }
      },

      getTabHasCount(tab: ResultsListTab): tab is ResultsListTabWithCount {
        return tab.count !== undefined
      },

      isActiveTab(tab: ResultsListTab): boolean {
        return this.internalTab == tab.href
      },
    },
  })
</script>

<style lang="css">
.results-list-tabs__icon {
  color: var(--grey-40);
}

.results-list-tabs__icon--active {
  color: var(--primary);
}

.results-list-tabs__label {
  margin: 0 var(--m-1);
}

.results-list-tabs__badge {
  background-color: var(--white);
  border-radius: 16px;
  font-weight: 400;
  padding: 0 8px;
  min-width: 24px;
  transition: 150ms all;
  font-size: 13px;
  letter-spacing: -0.1px;
  line-height: 18px;
}

.results-list-tabs__badge--active {
  background-color: var(--primary);
  color: var(--white);
}
</style>
