<script>
export default {
  name: 'SchemaFields',
  props: {
    items: { type: Object, default: () => {} },
    includeDepracated: { type: Boolean, default: false }
  }
}
</script>

<template>
  <v-list v-if="items">
    <v-list-group class="pa-2" prepend-icon="clear_all" no-action>
      <template v-slot:activator>
        <v-list-item-content>
          <div style="color: #f77062;">Fields</div>
        </v-list-item-content>
      </template>

      <v-list-item>
        <v-list-item-content>
          <div v-for="field in items" :key="field.name" class="pa-2">
            <div v-if="field.isDepracated ? includeDepracated : true">
              <div class="body-2 font-weight-medium">{{ field.name }}</div>
              <div class="caption">{{ field.description }}</div>

              <div class="caption">
                <span v-if="field.type.name">{{ field.type.name }}</span>
                <span v-if="field.type.ofType && field.type.ofType.name">
                  {{ field.type.ofType.name }}
                </span>
                <span
                  v-if="
                    field.type.ofType &&
                      field.type.ofType.ofType &&
                      field.type.ofType.ofType.name
                  "
                >
                  {{ field.type.ofType.ofType.name }}
                </span>
              </div>
            </div>
          </div>
        </v-list-item-content>
      </v-list-item>
    </v-list-group>
  </v-list>
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
