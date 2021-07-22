from enum import Enum


class StateType(Enum):
    Running = "Running"
    Completed = "Completed"
    Failed = "Failed"
    Scheduled = "Scheduled"
    Pending = "Pending"
