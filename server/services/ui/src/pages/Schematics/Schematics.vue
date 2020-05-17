<script>
export default {
  data() {
    return {}
  },
  watch: {
    authorizationToken(val) {
      if (val) {
        this.$apollo.queries.flows.refetch()
      }
    },
    flows(val) {
      if (!val) return
      if (!this.$route.params || !this.$route.params.id) {
        if (val[0]) {
          this.$router.push({ params: { id: val[0].id } })
        }
      }
    }
  },
  apollo: {
    flows: {
      query: require('@/graphql/Schematics/flow-list.gql'),
      update: data => {
        if (data.flow) return data.flow
      },
      fetchPolicy: 'no-cache'
    }
  }
}
</script>

<template>
  <div class="h-100 w-100 pa-0 ma-0">
    <v-navigation-drawer
      clipped
      left
      app
      permanent
      touchless
      :mini-variant="$vuetify.breakpoint.smAndDown"
    >
      <template v-slot:prepend>
        <v-list-item>
          <v-list-item-avatar>
            <v-icon class="blue--text accent-4">
              account_tree
            </v-icon>
          </v-list-item-avatar>
          <v-list-item-content>
            <div class="font-weight-medium">
              Flow Schematics
            </div>
          </v-list-item-content>
        </v-list-item>
      </template>

      <v-divider />

      <v-list dense>
        <v-list-item
          v-for="flow in flows"
          :key="flow.id"
          :to="{ params: { id: flow.id } }"
          ripple
          exact
        >
          <v-list-item-action>
            <v-icon>timeline</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>{{ flow.name }}</v-list-item-title>
            <v-list-item-subtitle class="id-subtitle">
              {{ flow.id }}
            </v-list-item-subtitle>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <router-view class="pa-0 grey lighten-5" style="min-height: 100%;" />
  </div>
</template>

<style lang="scss" scoped>
svg {
  cursor: grab;
  user-select: none;

  &:active {
    cursor: grabbing;
  }
}

.id-subtitle {
  font-size: 0.6rem !important;
}

.position-relative {
  position: relative;
}

.h-100 {
  height: calc(100vh - 64px);
}
</style>
