<script>
import { changeStateMixin } from '@/mixins/changeStateMixin'

export default {
  mixins: [changeStateMixin]
}
</script>

<template>
  <div v-if="dialogType == 'flow run'">
    <v-tooltip bottom>
      <template v-slot:activator="{ on }">
        <div v-on="on">
          <v-btn
            color="red darken-3"
            class="vertical-button white--text"
            :style="{ height: '46px' }"
            :disabled="!checkVersion || flowRun.state !== 'Running'"
            text
            small
            depressed
            :loading="cancelLoad"
            @click="cancelFlowRun"
          >
            <v-icon>not_interested</v-icon>
            Cancel
          </v-btn>
        </div>
      </template>
      <span v-if="!checkVersion">
        Upgrade your flow to Prefect 7.3 or higher to enable cancellation.
      </span>
      <span v-else-if="flowRun.state !== 'Running'">
        You cannot cancel a flow that's not running
      </span>
      <span v-else>Cancel a flow run</span>
    </v-tooltip>
  </div>
</template>
