<script>
import SchemaFields from './Schema-Fields'

export default {
  name: 'SchemaType',
  components: {
    SchemaFields
  },
  props: {
    type: {
      // /** @typedef {import('graphql').GraphQLType} GraphQLType */
      // This doesn't pass webpack compilation so disabling for now...
      // we can reinstate with TS
      type: null,
      required: true
    },
    arg: {
      type: Object,
      required: true
    }
  }
}
</script>

<template>
  <div v-if="type.name">
    <div class="overline type">
      {{ type.name }}
      <v-tooltip v-if="type.description" top>
        <template v-slot:activator="{ on }">
          <v-icon x-small v-on="on">
            help_outline
          </v-icon>
        </template>
        {{ type.description }}
      </v-tooltip>
    </div>
    <div class="subtitle-1 font-weight-bold">{{ arg.name }}</div>
    <div class="caption">{{ arg.description }}</div>

    <div v-if="type._fields" class="my-3">
      <SchemaFields :items="type._fields" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.type {
  color: #f77062;
  line-height: 1rem;

  &.query {
    color: #0073df !important;
  }

  &.mutation {
    color: #da2072 !important;
  }
}
</style>
