<template>
  <div ref="el" class="virtual-scroller">
    <div class="virtual-scroller__inner">
      <template v-for="(div, index) in divs" :key="index">
        <div :ref="hack.refs" class="virtual-scroller__item" :style="`transform: translateY(${div.distance}px)`" :data-index="index">
          <slot :item="items[div.item]" />
        </div>
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
  /* eslint-disable */
  import { onMounted, Ref, ref, reactive, computed, nextTick } from 'vue'

  type ItemProp = Record<string, any>
  type Div = {
    distance: number
    item: number
  }

  const props = defineProps<{
    items: ItemProp[],
    pageMode?: boolean
  }>()

  const el = ref<HTMLDivElement>()
  const divs = reactive<Div[]>([])

  // https://github.com/vuejs/core/issues/5525
  const hack = { refs: ref<HTMLDivElement[]>([]) }
  const itemRefs = computed(() => hack.refs.value)

  let intersectionObserver: IntersectionObserver | null = null
  let resizeObserver: ResizeObserver | null = null

  function intersect(entries: IntersectionObserverEntry[]): void {
    const items = getItemsRect()
    const container = getContainerRect()
    const offsetTop = container.top - items.top
    const offsetBottom = items.bottom - container.bottom

    const hidden = entries.filter(entry => !entry.isIntersecting)

    if(offsetTop == 0 || offsetBottom == 0 || hidden.length == 0) {
      return
    }

    // moving up or down? 
    const direction = offsetTop < offsetBottom ? 'up' : 'down'

    hidden.forEach(entry => {
      const index = getElementIndex(entry.target as HTMLElement)
      const div = divs[index]

      moveDiv(div, direction)
    })

    console.log({ direction, hidden })
  }

  function getElementIndex(element: HTMLElement): number {
    const value = element.dataset.index!
    const parsed = parseInt(value)

    return parsed
  }

  function moveDiv(div: Div, direction: 'up' | 'down'): void {
    requestAnimationFrame(() => {
      const { height } = getItemsRect()
      const rounded = Math.round(height)
      const distance = direction === 'down' ? rounded : rounded * -1
      const item = direction === 'down' ? getNextItemToRender() : getPreviousItemToRender()

      console.log({ rounded })
  
      if(item === null) {
        return
      }
  
      div.item = item
      div.distance = div.distance + distance
    })
  }

  function startIntersectionObserver(): void {
    if(intersectionObserver) {
      itemRefs.value.forEach(element => intersectionObserver!.observe(element))
    }
  }

  function startResizeObserver(): void {
    if(resizeObserver && el.value) {
      resizeObserver.observe(el.value)
    }
  }

  function isContainerFull() {
    const { height: containerHeight } = getContainerRect()
    const { height: itemsHeight } = getItemsRect()

    return itemsHeight >= containerHeight
  }

  function allItemsRendered() {
    return divs.length == props.items.length
  }

  function getItemsRect(): DOMRect {
    let first = true

    return itemRefs.value.reduce((acc, item) => {
      const itemRect = item.getBoundingClientRect()

      if(first) {
        first = false
        return itemRect
      }

      const x = Math.min(acc.x, itemRect.x)
      const y = Math.min(acc.y, itemRect.y)
      const width = Math.abs(Math.max(acc.right, itemRect.right) - Math.min(acc.left, itemRect.left))
      const height = Math.abs(Math.max(acc.bottom, itemRect.bottom) - Math.min(acc.top, itemRect.top))

      return new DOMRect(x, y, width, height)
    }, new DOMRect())
  }

  function getContainer(): HTMLElement | undefined {
    return props.pageMode ? document.body : el.value
  }

  function getContainerRect(): DOMRect {
    return getContainer()?.getBoundingClientRect() ?? new DOMRect()
  }

  function getLastRenderedItem(): number {
    return divs.reduce((last, { item }) => {
      return item > last ? item : last
    }, -Infinity)
  }

  function getFirstRenderedItem(): number {
    return divs.reduce((first, { item }) => {
      return item < first ? item : first
    }, Infinity)
  }

  function getPreviousItemToRender(): number | null {
    const firstRendered = getFirstRenderedItem()

    if(firstRendered === 0) {
      return null
    }

    return firstRendered - 1
  }

  function getNextItemToRender(): number | null {
    const lastRendered = getLastRenderedItem()

    if(lastRendered === props.items.length - 1) {
      return null
    }

    return lastRendered + 1
  }


  function addItem(): void {
    const last = getLastRenderedItem()
    const next = isFinite(last) ? last + 1 : 0

    console.log({ last, next })

    divs.push({
      distance: 0,
      item: next
    })
  }

  async function render(): Promise<void> {
    return new Promise(resolve => {
      requestAnimationFrame(() => resolve())
    })
  } 

  async function fillContainer(): Promise<void> {
    return new Promise(async resolve => {
      if(isContainerFull() || allItemsRendered()) {
        return resolve()
      }

      addItem()

      await nextTick()
      await render()
      
      return fillContainer().then(resolve)
    })
  }

  function resize(): void {
    console.log('resize')
  }

  function createIntersectionObserver(): void {
    intersectionObserver = new IntersectionObserver(intersect, {
      root: getContainer(),
      threshold: 0.1
    })
  }

  function createResizeObserver(): void {
    resizeObserver = new ResizeObserver(resize)
  }

  async function init(): Promise<void> {
    createIntersectionObserver()
    createResizeObserver()

    // or fill page
    await fillContainer()

    startIntersectionObserver()
    startResizeObserver()
  }

  onMounted(init)

</script>

<style lang="scss">
.virtual-scroller {
  overflow-y: scroll;
  height: 200px;
}

.virtual-scroller__inner {
  height: 1000px;
  overflow: hidden;
}
</style>