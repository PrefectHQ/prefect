<script>
import SchemaType from './Schema-Type'
import SchemaFields from './Schema-Fields'

export default {
  components: {
    SchemaType,
    SchemaFields
  },
  props: {
    schema: { type: Array, default: () => [] }
  },
  data() {
    return {
      typeColors: {
        query: '',
        mutation: ''
      }
    }
  },
  computed: {
    typeClass(type) {
      return { queryType: type == 'query', mutationType: type == 'mutation' }
    }
  },
  methods: {
    selectSchema(val) {
      this.$emit('select-schema', val)
    }
  }
}
</script>

<template>
  <v-container>
    <transition-group name="schema-item">
      <v-list
        v-if="schema.length !== 1"
        key="schema-item-1"
        class="elevation-2"
      >
        <transition-group name="schema-list-item">
          <v-list-item
            v-if="!schema.length"
            key="schema-list-item-1"
            class="schema-list-item"
          >
            <v-list-item-content>
              <v-list-item-title>No schema results found</v-list-item-title>
              <v-list-item-subtitle class="caption">
                Try broadening your search?
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>

          <v-list-item
            v-for="(item, index) in schema"
            :key="item.name"
            class="schema-list-item"
            @click="selectSchema(item.name)"
          >
            <v-list-item-content>
              <div v-if="index !== 0" class="separator"></div>

              <v-list-item-subtitle class="overline type" :class="item.action">
                {{ item.action }}
              </v-list-item-subtitle>
              <v-list-item-title>{{ item.name }}</v-list-item-title>
              <v-list-item-subtitle class="caption">
                {{ item.description }}
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </transition-group>
      </v-list>
      <v-card v-else key="schema-item-3" class="pa-4 schema-item">
        <div v-for="item in schema" :key="item.name">
          <div class="overline type" :class="item.action">
            {{ item.action }}
          </div>
          <div class="title">{{ item.name }}</div>
          <div class="subtitle-1">{{ item.description }}</div>

          <div class="separator my-5"></div>

          <v-list>
            <v-list-group class="pa-2" prepend-icon="sort" no-action>
              <template v-slot:activator>
                <v-list-item-content>
                  <div style="color: #f77062;">
                    Arguments
                  </div>
                </v-list-item-content>
              </template>

              <v-list-item>
                <v-list-item-content>
                  <div
                    v-for="(arg, index) in item.args"
                    :key="arg.name"
                    class="pa-2"
                  >
                    <div v-if="index !== 0" class="separator small mb-4"></div>

                    <SchemaType
                      v-if="arg.type.name"
                      :type="arg.type"
                      :arg="arg"
                    />
                    <SchemaType
                      v-if="arg.type.ofType && arg.type.ofType.name"
                      :type="arg.type.ofType"
                      :arg="arg"
                    />
                    <SchemaType
                      v-if="
                        arg.type.ofType &&
                          arg.type.ofType.ofType &&
                          arg.type.ofType.ofType.name
                      "
                      :type="arg.type.ofType.ofType"
                      :arg="arg"
                    />
                  </div>
                </v-list-item-content>
              </v-list-item>
            </v-list-group>
          </v-list>

          <div class="my-3">
            <SchemaFields v-if="item.type._fields" :items="item.type._fields" />
            <SchemaFields
              v-if="item.type.ofType && item.type.ofType._fields"
              :items="item.type.ofType._fields"
            />
            <SchemaFields
              v-if="
                item.type.ofType &&
                  item.type.ofType.ofType &&
                  item.type.ofType.ofType._fields
              "
              :items="item.type.ofType.ofType._fields"
            />

            <SchemaFields
              v-if="
                item.type.ofType &&
                  item.type.ofType.ofType &&
                  item.type.ofType.ofType.ofType &&
                  item.type.ofType.ofType.ofType._fields
              "
              :items="item.type.ofType.ofType.ofType._fields"
            />
          </div>
        </div>
      </v-card>
    </transition-group>
  </v-container>
</template>

<style lang="scss" scoped>
.separator {
  background-color: #eee;
  height: 1px;
  width: 100%;

  &.small {
    width: 75%;
  }
}

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

.schema-list-item {
  background-color: #fff;
  cursor: pointer;
}

.v-list-item {
  user-select: initial !important;
}

.schema-list-item,
.schema-item {
  transition: all 500ms;
}

.schema-list-item-enter,
.schema-list-item-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.schema-item-enter,
.schema-item-leave-to {
  opacity: 0;
  transform: translateY(-30px);
}

.schema-list-item-leave-active,
.schema-item-leave-active {
  position: absolute;
}
</style>
