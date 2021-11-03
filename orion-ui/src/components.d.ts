import Row from '@/components/Global/Row/Row.vue'
import ButtonCard from '@/components/Global/Button--Card/Button--Card.vue'
import BreadCrumbs from '@/components/Global/BreadCrumbs/BreadCrumbs.vue'
import RoundedButton from '@/components/Global/Rounded--Button/Rounded--Button.vue'
import Drawer from '@/components/Global/Drawer/Drawer.vue'
import List from '@/components/Global/List/List.vue'
import ListItem from '@/components/Global/ListItem/ListItem.vue'
import DeploymentListItem from '@/components/Global/DeploymentListItem/DeploymentListItem.vue'
import FlowListItem from '@/components/Global/FlowListItem/FlowListItem.vue'
import FlowRunListItem from '@/components/Global/FlowRunListItem/FlowRunListItem.vue'
import TaskRunListItem from '@/components/Global/TaskRunListItem/TaskRunListItem.vue'
import ResultsList from '@/components/Global/ResultsList/ResultsList.vue'

declare module 'vue' {
  export interface GlobalComponents {
    row: typeof Row
    'button-card': typeof ButtonCard
    'bread-crumbs': typeof BreadCrumbs
    'rounded-button': typeof RoundedButton
    drawer: typeof Drawer
    list: typeof List
    'list-item': typeof ListItem
    'deployment-list-item': typeof DeploymentListItem
    'flow-list-item': typeof FlowListItem
    'flow-run-list-item': typeof FlowRunListItem
    'task-run-list-item': typeof TaskRunListItem
    'results-list': typeof ResultsList
  }
}

export {}
