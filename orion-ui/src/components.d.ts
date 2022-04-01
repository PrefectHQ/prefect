import ButtonCard from '@/components/Global/ButtonCard/ButtonCard.vue'
import DeploymentListItem from '@/components/Global/DeploymentListItem/DeploymentListItem.vue'
import FlowListItem from '@/components/Global/FlowListItem/FlowListItem.vue'
import FlowRunListItem from '@/components/Global/FlowRunListItem/FlowRunListItem.vue'
import List from '@/components/Global/List/List.vue'
import ListItem from '@/components/Global/ListItem/ListItem.vue'
import ResultsList from '@/components/Global/ResultsList/ResultsList.vue'
import RoundedButton from '@/components/Global/RoundedButton/RoundedButton.vue'
import Row from '@/components/Global/Row/Row.vue'
import StateIcon from '@/components/Global/StateIcon/StateIcon.vue'
import TaskRunListItem from '@/components/Global/TaskRunListItem/TaskRunListItem.vue'

declare module 'vue' {
  export interface GlobalComponents {
    Row: typeof Row,
    ButtonCard: typeof ButtonCard,
    RoundedButton: typeof RoundedButton,
    List: typeof List,
    ListItem: typeof ListItem,
    DeploymentListItem: typeof DeploymentListItem,
    FlowListItem: typeof FlowListItem,
    FlowRunListItem: typeof FlowRunListItem,
    TaskRunListItem: typeof TaskRunListItem,
    ResultsList: typeof ResultsList,
    StateIcon: typeof StateIcon,
  }
}
