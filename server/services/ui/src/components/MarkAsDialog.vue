<script>
import { changeStateMixin } from '@/mixins/changeStateMixin'

export default {
  mixins: [changeStateMixin]
}
</script>

<template>
  <div v-if="activeButton()">
    <v-dialog v-model="markAsDialog" width="500" @click:outside="reset">
      <template v-slot:activator="{ on: dialog }">
        <v-tooltip bottom>
          <template #activator="{ on: tooltip }">
            <div v-on="{ ...tooltip, ...dialog }">
              <v-btn
                class="vertical-button"
                :style="{ height: '46px' }"
                text
                small
                depressed
                color="grey darken-2"
              >
                <v-icon>label_important</v-icon>
                <div>Mark As</div>
              </v-btn>
            </div>
          </template>
          <span>Change the state of this {{ dialogType }}</span>
        </v-tooltip>
      </template>
      <v-card :loading="markAsLoading">
        <v-card-title>
          Change the state of {{ taskRun ? taskRun.name : flowRun.name }}
        </v-card-title>
        <v-card-text>
          <v-stepper v-model="e1">
            <v-stepper-header>
              <v-stepper-step :complete="e1 > 1" editable step="1">
                Select State
              </v-stepper-step>
              <v-divider></v-divider>
              <v-stepper-step :complete="e1 > 2" step="2">
                Confirm
              </v-stepper-step>
            </v-stepper-header>
            <v-divider></v-divider>
            <v-stepper-items>
              <v-stepper-content step="1">
                <v-card-text>
                  <div>
                    <v-autocomplete
                      v-model="selectedState"
                      label="Select A State"
                      :items="filteredStates"
                      autocomplete="new-password"
                      required
                    >
                    </v-autocomplete>
                  </div>
                  <v-checkbox
                    v-if="flowRun"
                    v-model="allTasks"
                    label="Change the state of all task runs too"
                  ></v-checkbox>
                  <v-form ref="form" @submit.prevent>
                    <v-text-field
                      v-model="reason"
                      autocomplete="off"
                      label="Optional - Why are you changing state?"
                      @keyup.enter="checkContinue()"
                    ></v-text-field>
                  </v-form>
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn color="primary" @click="checkContinue">
                    Continue
                  </v-btn>

                  <v-btn text @click="reset">Cancel</v-btn>
                </v-card-actions>
              </v-stepper-content>

              <v-stepper-content step="2">
                <v-card-text>
                  Please be aware that clicking on confirm will set the state of
                  your
                  {{ dialogType }}
                  {{ taskRun ? taskRun.name : flowRun.name }} to
                  <span class="font-weight-black pb-8">
                    {{ selectedState }}.</span
                  >
                  <span v-if="dialogType === 'task run'">
                    This may have an effect on downstream tasks.
                  </span>
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn color="primary" @click="changeState">
                    Confirm
                  </v-btn>
                  <v-btn text @click="reset">Cancel</v-btn>
                </v-card-actions>
              </v-stepper-content>
            </v-stepper-items>
          </v-stepper>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
  <div v-else-if="dialogType == 'task run'">
    <v-tooltip bottom>
      <template v-slot:activator="{ on }">
        <div v-on="on">
          <v-btn
            text
            disabled
            class="vertical-button"
            :style="{ height: '46px' }"
            small
            depressed
            color="grey darken-2"
          >
            <v-icon>label_important</v-icon>
            Mark As
          </v-btn>
        </div>
      </template>
      <span>
        You can only change the marked state of a finished task-run
      </span>
    </v-tooltip>
  </div>
</template>

<style>
.theme--light.v-subheader {
  color: #000;
  font-weight: bold !important;
}
</style>
