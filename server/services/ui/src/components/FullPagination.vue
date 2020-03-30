<script>
export default {
  props: {
    countOptions: {
      type: Array,
      default: () => [10, 20, 50],
      validator: countOptions => {
        // expecting an array of integers with a length > 0
        return countOptions.length > 0
      }
    },
    page: {
      required: true,
      type: Number,
      validator: page => page > 0
    },
    totalItems: {
      required: true,
      type: Number,
      validator: totalItems => totalItems > 0
    }
  },
  data() {
    return {
      selected: this.countOptions[0]
    }
  },
  computed: {
    disableDecrementPage() {
      return this.page === 1
    },
    disableIncrementPage() {
      return this.endingNumber >= this.totalItems
    },
    endingNumber() {
      const product = this.selected * this.page
      if (product <= this.totalItems) return product

      return this.totalItems
    },
    startingNumber() {
      if (this.page === 1) {
        return 1
      }
      return (this.page - 1) * this.selected + 1
    },
    style() {
      return { width: `${this.selected.toString().length * 25}px` }
    }
  },
  methods: {
    handleChange(newCount) {
      this.$emit('change-page', 1)
      this.$emit('change-count-option', newCount)
    },
    handleDecrementPage() {
      if (this.page > 1) {
        this.$emit('change-page', this.page - 1)
      }
    },
    handleIncrementPage() {
      if (this.page * this.selected <= this.totalItems) {
        this.$emit('change-page', this.page + 1)
      }
    }
  }
}
</script>

<template>
  <div class="d-flex justify-end align-center">
    <div class="d-flex align-baseline justify-end">
      <div class="mr-2 caption black--text">
        Items per page:
      </div>
      <div :style="style">
        <v-select
          v-model="selected"
          class="caption"
          hide-details
          :items="countOptions"
          @change="handleChange"
        />
      </div>
      <div class="caption mx-5 black--text">
        {{ startingNumber }}-{{ endingNumber }} of {{ totalItems }}
      </div>
      <div>
        <v-btn
          icon
          :disabled="disableDecrementPage"
          @click="handleDecrementPage"
        >
          <v-icon>chevron_left</v-icon>
        </v-btn>
        <v-btn
          icon
          :disabled="disableIncrementPage"
          @click="handleIncrementPage"
        >
          <v-icon>chevron_right</v-icon>
        </v-btn>
      </div>
    </div>
  </div>
</template>
