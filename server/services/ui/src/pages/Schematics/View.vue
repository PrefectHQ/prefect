<script>
import SchematicFlow from '@/components/Schematics/Schematic-Flow'

export default {
  components: {
    SchematicFlow
  },
  data() {
    return {
      flow: null,
      loading: 0,
      tasks: []
    }
  },
  apollo: {
    flow: {
      query: require('@/graphql/Schematics/flow.gql'),
      loadingKey: 'loading',
      variables() {
        return {
          id: this.$route.params.id
        }
      },
      skip() {
        return !this.$route.params.id
      },
      update(data) {
        if (data.flow && data.flow.length) {
          this.tasks = data.flow[0].tasks
          return data.flow[0]
        } else {
          this.tasks = []
        }
      }
    }
  }
}
</script>

<template>
  <v-container class="ma-0 pa-0 fill-height" fluid>
    <v-card
      v-if="!$route.params.id && loading === 0"
      class="no-flows pa-10 text-center"
    >
      <div class="my-4 display-1">You have no flows 🤖</div>
    </v-card>

    <v-row no-gutters>
      <v-col class="full-height">
        <SchematicFlow :dev-toolbar="true" :tasks="tasks" />
      </v-col>
    </v-row>
  </v-container>
</template>

<style lang="scss" scoped>
.full-height {
  height: calc(100vh - 64px) !important;
  min-height: calc(100vh - 64px) !important;
}
</style>
