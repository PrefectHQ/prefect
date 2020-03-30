<script>
export default {
  props: {
    genericInput: {
      required: true,
      type: Object,
      validator: input => {
        return !!input.item.id
      }
    }
  }
}
</script>

<template>
  <v-container class="side-drawer-flow-runs mb-10 pb-10">
    <v-layout column class="mb-5">
      <v-flex xs 12>
        <v-icon small :color="genericInput.item.state" class="mr-1">
          brightness_1
        </v-icon>
        <span class="title">
          {{ genericInput.item.state }}
        </span>
      </v-flex>
    </v-layout>

    <v-layout class="my-2">
      <v-flex xs6 class="text-left body-1 font-weight-medium">
        Message
      </v-flex>
      <v-flex xs6 class="text-right body-1 message-overflow">
        {{ genericInput.item.message }}
      </v-flex>
    </v-layout>
    <v-layout class="my-2">
      <v-flex xs6 class="text-left body-1 font-weight-medium">
        Time
      </v-flex>
      <v-flex xs6 class="text-right body-1">
        {{ genericInput.item.timestamp | displayDateTime }}
      </v-flex>
    </v-layout>
  </v-container>
</template>

<style lang="scss" scoped>
.side-drawer-flow-runs {
  overflow-y: scroll;
}

.message-overflow {
  overflow-wrap: break-word;
}
</style>
