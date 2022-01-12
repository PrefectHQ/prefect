<template>
  <div class="button-group-input">
    <template v-for="(item, index) in items" :key="index">
      <button type="button" class="button-group-input__button" :class="getItemClass(item)" @click="toggleItem(item)">
        <slot v-bind="{ item }">
          {{ item }}
        </slot>
      </button>
    </template>
  </div>
</template>

<script lang="ts">
  import { PropType, defineComponent } from 'vue'

  export default defineComponent({
    name: 'ButtonGroupInput',
    expose: [],
    props: {
      items: {
        type: Array as PropType<(string | number)[]>,
        required: true,
      },

      value: {
        type: Array as PropType<(string | number)[]>,
        required: true,
      },
    },

    emits: ['update:value'],
    computed: {
      internalValue: {
        get: function() {
          return this.value
        },

        set: function(value: (string | number)[]) {
          this.$emit('update:value', value)
        },
      },
    },

    methods: {
      toggleItem(item: string | number) {
        const index = this.internalValue.indexOf(item)

        if (index >= 0) {
          this.internalValue.splice(index, 1)
        } else {
          this.internalValue.push(item)
        }
      },

      getItemClass(item: string | number) {
        return {
          'button-group-input__button--selected': this.value.includes(item),
        }
      },
    },
  })
</script>

<style lang="scss">
.button-group-input {
  border: 1px solid #CECDD3;
  display: flex;
  border-radius: 4px;
  overflow: hidden;
}

.button-group-input__button {
  appearance: none;
  cursor: pointer;
  border: 0;
  background-color: var(--grey-10);
  color: var(--grey-80);
  font-family: 'input-sans';
  font-size: 12px;
  padding: var(--p-1) var(--p-2);
  padding-bottom: calc(var(--p-1) - 2px);

  &:not(:last-child) {
    border-right: 1px solid #CECDD3;
  }

  &:hover {
    background-color: var(--secondary-hover);
  }

  &:active {
    background-color: var(--secondary-pressed);
  }
}

.button-group-input__button--selected {
  background-color: var(--primary);
  color: #fff;

  &:hover {
    background-color: var(--primary-hover);
  }

  &:active {
    background-color: var(--primary-pressed);
  }
}
</style>