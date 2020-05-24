<script>
import gql from 'graphql-tag'

export default {
  components: {},
  props: {
    flow: {
      type: Object,
      default: null
    },
    type: {
      type: String,
      default: null
    }
  },
  data() {
    return {
      dialog: false,
      deleting: false,
      errorMessage: '',
      allFlows: false,
      deleteDialog: false
    }
  },
  computed: {
    all() {
      if (this.allFlows) return true
      if (this.type === 'fvg') return true
      return false
    },
    mutationString() {
      if (!this.all) {
        return gql`
          mutation($flowId: UUID!) {
            delete_flow(input: { flow_id: $flowId }) {
              success
            }
          }
        `
      } else {
        let string = this.versionGroup.map((flow, ind) => {
          return `delete${ind}: delete_flow(input: { flow_id: "${flow.id}" }) {
              success
            }`
        })
        const newString = gql`
          mutation {
            ${string}
          }
        `
        return newString
      }
    }
  },
  methods: {
    async deleteFlow() {
      try {
        this.deleting = true
        const { data } = await this.$apollo.mutate({
          mutation: this.mutationString,
          variables: {
            flowId: this.flow.id
          }
        })
        if (!this.all && data?.delete_flow?.success) {
          this.deleting = false
          this.$router.push({ name: 'dashboard' })
          this.$toasted.show(
            `Version ${this.flow.version} of ${this.flow.name} Deleted`,
            {
              containerClass: 'toast-typography',
              icon: 'delete_forever',
              action: {
                text: 'Close',
                onClick(e, toastObject) {
                  toastObject.goAway(0)
                }
              },
              duration: 2000
            }
          )
        } else if (this.all && data?.delete0?.success) {
          this.deleting = false
          if (this.type === 'flow') {
            this.$router.push({ name: 'dashboard' })
          } else {
            this.$emit('refetch')
            this.reset()
          }
          this.$toasted.show(`All versions of ${this.flow.name} deleted`, {
            containerClass: 'toast-typography',
            icon: 'delete_forever',
            action: {
              text: 'Close',
              onClick(e, toastObject) {
                toastObject.goAway(0)
              }
            },
            duration: 2000
          })
        } else {
          this.deleting = false
          this.errorMessage =
            'We could not delete your flow.  Please try again.  If this problem continues, contact help@prefect.io'
        }
      } catch (error) {
        this.deleting = false
        this.errorMessage =
          'We could not delete your flow.  Please try again.  If this problem continues, contact help@prefect.io'
      }
    },
    reset() {
      this.dialog = false
      this.deleting = false
      this.errorMessage = ''
      this.allFlows = false
      this.deleteDialog = false
    }
  },
  apollo: {
    versionGroup: {
      query: require('@/graphql/Flow/version-group.gql'),
      variables() {
        return {
          vgi: this.flow.version_group_id
        }
      },
      pollInterval: 1000,
      update: data => data.flow
    }
  }
}
</script>

<template>
  <div class="text-center">
    <v-dialog v-model="deleteDialog" width="500" @click:outside="reset">
      <template v-slot:activator="{ on: dialog }">
        <v-tooltip bottom>
          <template #activator="{ on: tooltip }">
            <div v-on="{ ...tooltip, ...dialog }">
              <v-btn
                class="vertical-button"
                text
                tile
                small
                color="red accent-2"
                aria-label="delete"
              >
                <v-icon>delete</v-icon>
                <div v-if="type === 'flow'">Delete</div>
              </v-btn>
            </div>
          </template>
          <span v-if="type === 'flow'">Delete this flow</span>
          <span v-if="type === 'fvg'">Delete this flow version group</span>
        </v-tooltip>
      </template>

      <!-- <template v-slot:activator="{ on }">
        <v-btn
          class="vertical-button"
          text
          tile
          small
          color="red accent-2"
          aria-label="delete"
          @click="dialog = true"
        >
          <v-icon>delete</v-icon>
          <div v-if="type === 'flow'">Delete</div>
        </v-btn>
      </template> -->

      <v-card :loading="deleting">
        <v-card-title v-if="!errorMessage && type === 'flow'">
          Delete flow "{{ flow.name }}" version {{ flow.version }}?
        </v-card-title>
        <v-card-title v-if="!errorMessage && type === 'fvg'">
          Delete all versions of this flow?
        </v-card-title>
        <v-card-text class="fix-height">
          <v-checkbox
            v-if="!errorMessage && type === 'flow'"
            v-model="allFlows"
            color="red accent-2"
            :label="`Delete all versions of this flow.`"
          ></v-checkbox>
          <div
            v-if="!errorMessage && !all && flow.archived === false"
            class="font-weight-bold"
          >
            This is an active version of your flow. Only archived versions will
            remain.
          </div>
          <div v-if="!errorMessage && all">
            This will delete <span class="font-weight-black">all </span>versions
            of your flow and cannot be undone.
          </div>
          <div class="red--text pt-5">
            {{ errorMessage }}
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            v-if="!errorMessage"
            color="red accent-2"
            class="white--text"
            @click="deleteFlow"
          >
            Delete
          </v-btn>
          <v-btn text @click="reset()">Cancel</v-btn>
        </v-card-actions></v-card
      >
    </v-dialog>
  </div>
</template>

<style scoped lang="scss">
.fix-height {
  height: 110px;
}
</style>
