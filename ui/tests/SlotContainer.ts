import { defineComponent, h as createVNode } from 'vue'

// Keep named slots visible while replacing unrelated design-system components.
export const SlotContainer = defineComponent({
  name: 'SlotContainer',
  setup: (_props, { slots }) => () => createVNode('div', Object.values(slots).flatMap(slot => slot?.() ?? [])),
})
