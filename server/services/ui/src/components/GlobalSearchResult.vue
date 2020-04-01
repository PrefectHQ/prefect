<script>
/* eslint-disable vue/no-v-html */
// Added this line to disable to the v-html
// console warning since we know we can trust the
// data coming from the GraphQL server
export default {
  props: {
    searchResult: {
      required: true,
      type: Object,
      validator: result => {
        return (
          result.id &&
          result.name &&
          ['flow', 'flow_run', 'task', 'task_run'].includes(result.__typename)
        )
      }
    },
    // This is a reference to the parent passed in by the VAutoComplete
    // component. It contains important search highlighting methods
    // but we don't use it for much else. It's typed as an Object
    // and we're making sure the .genFilteredText() method exists on the
    // passed prop.
    parent: {
      type: Object,
      required: true,
      validator: parent => {
        return parent.genFilteredText
      }
    }
  },
  computed: {
    // Here we're just translating the
    // __typename reference to a human-readable format.
    // We could do this with a regex if we wanted.
    typeName() {
      switch (this.searchResult.__typename) {
        case 'flow':
          return 'Flow'
        case 'flow_run':
          return 'Flow Run'
        case 'task':
          return 'Task'
        case 'task_run':
          return 'Task Run'
        default:
          return ''
      }
    }
  }
}
</script>

<template>
  <div class="search-result">
    <v-list-item-content>
      <v-list-item-subtitle>{{ typeName }}</v-list-item-subtitle>
      <!-- the .genFilteredText() method calls a number of downstream methods
       on the parent component. This allows us to show where the user input
      matches the results we're returning to them.
      Since it returns HTML, we need to use the Vue HTML injector, otherwise
      it'll be inserted as plaintext. -->
      <v-list-item-title
        v-html="`${parent.genFilteredText(searchResult.name)}`"
      />
      <v-list-item-subtitle class="id-subtitle">
        {{ searchResult.id }}
      </v-list-item-subtitle>
    </v-list-item-content>
  </div>
</template>

<style lang="scss" scoped>
.search-result {
  cursor: pointer;
  min-width: 15rem;
}

.id-subtitle {
  font-size: 0.6rem !important;
}

.text--secondary {
  background-color: #123456 !important;
}
</style>
