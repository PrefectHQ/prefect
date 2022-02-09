<template>
  <i class="pi" :class="classes" :style="styles" />
</template>

<script lang="ts">
  import { ClassValue } from '@/types/css'
  import { StateColors, StateIcons } from '@/types/states'
  import { IconSize, getIconSizeClass } from '@/utilities/icons'
  import { isState } from '@/utilities/states'
  import { StyleValue } from '@vue/runtime-dom'
  import { defineComponent, PropType } from 'vue'
  import { StateType } from '../models/StateType'

  export default defineComponent({
    name: 'StateTypeIcon',
    expose: [],
    props: {
      type: {
        type: String as PropType<StateType>,
        required: true,
        validator: isState,
      },

      size: {
        type: String as PropType<IconSize>,
        default: null,
      },

      colored: {
        type: Boolean,
      },
    },

    computed: {
      classes: function(): ClassValue {
        const iconClass = StateIcons.get(this.type)!
        const sizeClass = getIconSizeClass(this.size)

        return [iconClass, sizeClass]
      },

      styles: function(): StyleValue {
        return {
          color: this.colored ? StateColors.get(this.type) : undefined,
        }
      },
    },
  })
</script>
