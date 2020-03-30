<script>
import gql from 'graphql-tag'
import Alert from '@/components/Alert'
import ConfirmDialog from '@/components/ConfirmDialog'
import ManagementLayout from '@/layouts/ManagementLayout'

export default {
  components: {
    Alert,
    ConfirmDialog,
    ManagementLayout
  },
  data() {
    return {
      // Table headers
      allHeaders: [
        {
          mobile: true,
          text: 'Name',
          value: 'name',
          width: '40%'
        },
        {
          mobile: true,
          text: 'Active',
          value: 'active',
          align: 'left',
          width: '20%'
        },
        {
          mobile: true,
          text: 'Group ID',
          value: 'version_group_id',
          width: '30%'
        },
        {
          mobile: true,
          text: '',
          value: 'action',
          align: 'end',
          sortable: false,
          width: '10%'
        }
      ],

      // Copying FVG ID
      copiedFvgId: null,
      copyTimeout: null,

      // Dialogs
      dialogDeleteFvg: false,

      // Load states
      flowsLoaded: false,
      fvgsLoaded: false,
      isDeletingFvg: false,
      isLoadingFvgs: false,

      // Search
      search: null,

      // FVG selected for deletion
      selectedFvg: null,

      // Alert data
      alertShow: false,
      alertMessage: '',
      alertType: null
    }
  },
  computed: {
    deleteFvgMutation() {
      if (!this.versionGroupFlows) return {}

      let mutation = this.versionGroupFlows.map(
        (flow, ind) =>
          `delete${ind}: delete_flow(input: { flow_id: "${flow.id}" }) {
            success
          }`
      )

      return gql`
        mutation DeleteFlowVersionGroup {
          ${mutation}
        }
      `
    },
    headers() {
      return this.$vuetify.breakpoint.mdAndUp
        ? this.allHeaders
        : this.allHeaders.filter(header => header.mobile)
    },
    isLoadingTable() {
      return !(this.flowsLoaded && this.fvgsLoaded)
    },
    items() {
      if (!(this.versionGroups && this.flows)) return []

      return this.versionGroups.map(item => ({
        ...item,
        active:
          this.flows.filter(
            flow => flow.version_group_id === item.version_group_id
          ).length > 0
      }))
    }
  },
  methods: {
    cancelFvgDelete() {
      this.selectedFvg = null
      this.dialogDeleteFvg = false
    },
    copyTextToClipboard(id) {
      clearTimeout(this.copyTimeout)

      this.copiedFvgId = id

      navigator.clipboard.writeText(id)

      this.copyTimeout = setTimeout(() => {
        this.copiedFvgId = null
      }, 3000)
    },
    async deleteFvg() {
      this.isDeletingFvg = true

      try {
        await this.$apollo.mutate({
          mutation: this.deleteFvgMutation
        })

        this.$apollo.queries.versionGroups.refetch()
        this.$apollo.queries.flows.refetch()

        this.handleSuccess(
          'The flow version group has been successfully deleted.'
        )
      } catch (e) {
        this.handleError(
          'Something went wrong while trying to delete this flow version group.'
        )
        throw Error(e)
      }

      this.dialogDeleteFvg = false
      this.isDeletingFvg = false
      this.selectedFvg = null
    },
    handleError(message) {
      this.alertType = 'error'
      this.alertMessage = `${message}. Please try again later. If this error persists, please contact help@prefect.io.`
      this.alertShow = true
    },
    handleSuccess(message) {
      this.alertType = 'success'
      this.alertMessage = message
      this.alertShow = true
    },
    selectFvg(fvg) {
      this.selectedFvg = fvg
    }
  },
  apollo: {
    versionGroupFlows: {
      query: require('@/graphql/Flow/version-group.gql'),
      variables() {
        return {
          vgi: this.selectedFvg.version_group_id
        }
      },
      update(data) {
        return data.flow
      },
      skip() {
        return !this.selectedFvg
      },
      error() {
        this.handleError(
          'Something went wrong while trying to fetch your flows.'
        )
      }
    },
    versionGroups: {
      query: require('@/graphql/VersionGroups/flow-version-groups.gql'),
      result({ data }) {
        if (!data) return
        this.fvgsLoaded = true
      },
      error() {
        this.handleError(
          'Something went wrong while trying to fetch your flows.'
        )
      },
      update(data) {
        return data.versionGroup
      },
      fetchPolicy: 'no-cache'
    },
    flows: {
      query: require('@/graphql/VersionGroups/flows.gql'),
      result({ data }) {
        if (!data) return
        this.flowsLoaded = true
      },
      error() {
        this.handleError(
          'Something went wrong while trying to fetch your flows.'
        )
      },
      update(data) {
        return data.flow
      },
      fetchPolicy: 'no-cache'
    }
  }
}
</script>

<template>
  <ManagementLayout :show="!isLoadingTable" control-show>
    <template v-slot:title>Flow Version Groups</template>

    <template v-slot:subtitle>
      <span>
        View and manage your flows by version group.
      </span>
    </template>

    <!-- SEARCH (MOBILE) -->
    <v-text-field
      v-if="!$vuetify.breakpoint.mdAndUp"
      v-model="search"
      class="rounded-none elevation-1 mt-2 mb-1"
      solo
      dense
      hide-details
      single-line
      placeholder="Search by flow name"
      prepend-inner-icon="search"
      autocomplete="new-password"
    ></v-text-field>

    <v-card :class="{ 'mt-3': $vuetify.breakpoint.mdAndUp }">
      <v-card-text class="pa-0">
        <!-- SEARCH (DESKTOP) -->
        <div v-if="$vuetify.breakpoint.mdAndUp" class="py-1 mr-2 flex">
          <v-text-field
            v-model="search"
            class="rounded-none elevation-1"
            solo
            dense
            hide-details
            single-line
            placeholder="Search by flow name"
            prepend-inner-icon="search"
            autocomplete="new-password"
            :style="{
              'max-width': $vuetify.breakpoint.mdAndUp ? '420px' : null
            }"
          ></v-text-field>
        </div>

        <!-- FVG TABLE -->
        <v-data-table
          fixed-header
          :search="search"
          :header-props="{ 'sort-icon': 'arrow_drop_up' }"
          :items="items"
          :headers="headers"
          :items-per-page="10"
          class="elevation-2 rounded-none"
          :class="{ 'fixed-table': $vuetify.breakpoint.smAndUp }"
          :footer-props="{
            showFirstLastPage: true,
            firstIcon: 'first_page',
            lastIcon: 'last_page',
            prevIcon: 'keyboard_arrow_left',
            nextIcon: 'keyboard_arrow_right'
          }"
        >
          <!-- HEADERS -->
          <template v-slot:header.name="{ header }">
            <span class="subtitle-2">{{ header.text.toUpperCase() }}</span>
          </template>
          <template v-slot:header.active="{ header }">
            <span class="subtitle-2">{{ header.text.toUpperCase() }}</span>
          </template>
          <template v-slot:header.version_group_id="{ header }">
            <span class="subtitle-2">{{ header.text.toUpperCase() }}</span>
          </template>

          <!-- FVG ID -->
          <template v-slot:item.version_group_id="{ item }">
            <v-tooltip top>
              <template v-slot:activator="{ on }">
                <div
                  class="hidewidth cursor-pointer"
                  v-on="on"
                  @click="copyTextToClipboard(item.version_group_id)"
                >
                  <span v-if="$vuetify.breakpoint.smAndUp">
                    {{ item.version_group_id }}
                  </span>
                  <span v-else>
                    {{ item.version_group_id.substring(0, 3) }}...
                  </span>
                </div>
              </template>
              <span>{{
                copiedFvgId === item.version_group_id
                  ? 'Copied!'
                  : 'Click to copy ID'
              }}</span>
            </v-tooltip>
          </template>

          <!-- FVG NAME -->
          <template v-slot:item.name="{ item }">
            <v-tooltip v-if="item.name" top>
              <template v-slot:activator="{ on }">
                <div class="hidewidth" v-on="on">
                  <router-link
                    :to="{
                      name: 'flow',
                      params: {
                        id: item.id
                      },
                      query: { versions: '' }
                    }"
                  >
                    {{ item.name }}
                  </router-link>
                </div>
              </template>
              <span>{{ item.name }}</span>
            </v-tooltip>
            <span v-else>-</span>
          </template>

          <!-- FVG ACTIVE/ARCHIVED -->
          <template v-slot:item.active="{ item }">
            <v-tooltip top>
              <template v-slot:activator="{ on }">
                <v-icon v-if="item.active" small dark color="green" v-on="on">
                  timeline
                </v-icon>
                <v-icon v-else small dark color="accent-pink" v-on="on">
                  archive
                </v-icon>
              </template>
              <span v-if="item.active">
                This version group has an active flow
              </span>
              <span v-else>
                All flows in this version group are archived
              </span>
            </v-tooltip>
          </template>

          <!-- FVG ACTIONS -->
          <template v-slot:item.action="{ item }">
            <v-btn
              color="error"
              text
              fab
              x-small
              @click="
                dialogDeleteFvg = true
                selectFvg(item)
              "
            >
              <v-icon>delete</v-icon>
            </v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <!-- DELETE FVG -->
    <ConfirmDialog
      v-if="selectedFvg"
      v-model="dialogDeleteFvg"
      type="error"
      :dialog-props="{ 'max-width': '500' }"
      :disabled="isDeletingFvg"
      :loading="isDeletingFvg"
      :title="
        `Are you sure you want to delete the version group for ${selectedFvg.name}?`
      "
      @cancel="cancelFvgDelete"
      @confirm="deleteFvg"
    >
      This will delete <span class="font-weight-black">all</span> versions of
      your flow and cannot be undone.
    </ConfirmDialog>

    <Alert
      v-model="alertShow"
      :type="alertType"
      :message="alertMessage"
      :offset-x="$vuetify.breakpoint.mdAndUp ? 256 : 56"
    ></Alert>
  </ManagementLayout>
</template>

<style lang="scss">
.cursor-pointer {
  cursor: pointer;
}

.hidewidth {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

.fixed-table {
  table {
    table-layout: fixed;
  }
}

.v-data-table {
  td {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>

<style lang="scss" scoped>
.flex {
  display: flex;
  justify-content: flex-end;
}
</style>
