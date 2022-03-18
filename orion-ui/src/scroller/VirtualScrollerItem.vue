<script lang="ts">
  import { defineComponent, h, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'

  export default defineComponent({
    name: 'VirtualScrollerItem',
    expose: [],
    props: {
      id: {
        required: true,
        type: String,
      },
    },

    emits: ['size'],

    setup(props, { emit, slots }) {
      const root = ref<HTMLDivElement>()
      const observer = new ResizeObserver(() => emitSize())

      function getSize(): { width: number, height: number } {
        if (!root.value) {
          return { width: 0, height: 0 }
        }

        const { width, height } = root.value.getBoundingClientRect()

        return { width, height }
      }

      function emitSize(): void {
        emit('size', {
          id: props.id,
          size: getSize(),
        })
      }

      function observe(): void {
        if (root.value) {
          observer.observe(root.value)
        }
      }

      onMounted(() => observe())

      onUpdated(() => emitSize())

      onBeforeUnmount(() => observer.disconnect())

      return () => h('div', {
        class: 'virtual-scroller-item',
        ref: root,
      }, slots.default ? slots.default() : undefined)
    },
  })
</script>