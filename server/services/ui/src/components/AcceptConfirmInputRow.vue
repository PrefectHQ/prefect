<script>
export default {
  props: {
    label: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      confirm: false
    }
  },
  methods: {
    accept() {
      this.$emit('accept')
      this.confirm = false
    },
    decline() {
      this.$emit('decline')
      this.confirm = false
    }
  }
}
</script>

<template>
  <v-list-item-content>
    <v-list-item-title class="fixed-height relative">
      <v-row v-if="!confirm">
        <v-col cols="5" class="truncate">
          <span class="blue-grey--text text--darken-1">{{ label }}</span>
        </v-col>
        <v-col cols="7" class="text-right">
          <v-btn
            small
            color="primary"
            text
            class="mx-1"
            @click="confirm = 'accept'"
          >
            <v-icon>
              check
            </v-icon>
          </v-btn>

          <v-btn
            small
            color="error"
            text
            class="mx-1"
            @click="confirm = 'decline'"
          >
            <v-icon>
              close
            </v-icon>
          </v-btn>
        </v-col>
      </v-row>

      <v-row v-else>
        <v-col cols="12">
          <v-btn
            v-if="confirm == 'accept'"
            color="primary"
            block
            text
            class="mx-1"
            @click="accept"
          >
            Accept
          </v-btn>
          <v-btn
            v-if="confirm == 'decline'"
            color="error"
            block
            text
            class="mx-1"
            @click="decline"
          >
            Decline
          </v-btn>
        </v-col>
      </v-row>
      <v-btn
        v-if="!!confirm"
        x-small
        icon
        class="cancel-button"
        @click="confirm = false"
      >
        <v-icon>close</v-icon>
      </v-btn>
    </v-list-item-title>
  </v-list-item-content>
</template>

<style lang="scss" scoped>
.fixed-height {
  height: 60px;
}

.truncate {
  line-height: 2em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cancel-button {
  position: absolute;
  right: 0;
  top: 0;
}
</style>
