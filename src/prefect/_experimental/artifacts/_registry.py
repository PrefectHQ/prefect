"""
Registry for tracking artifact component relationships.
"""
from typing import Protocol, Union
from uuid import UUID


class SyncableArtifact(Protocol):
    """Protocol for artifacts that can be synced."""
    id: UUID
    
    def _update(self) -> None:
        """Update the artifact."""
        ...

    async def _aupdate(self) -> None:
        """Update the artifact."""
        ...


class ArtifactRegistry:
    """
    Registry to track which artifacts contain which ArtifactComponent objects.
    This avoids circular references by only tracking relationships.
    """
    _component_to_artifacts: dict[UUID, set[UUID]] = {}
    _artifact_components: dict[UUID, set[UUID]] = {}
    _artifact_instances: dict[UUID, SyncableArtifact] = {}  # Store artifact instances for syncing
    
    @classmethod
    def register_component(cls, component_id: UUID, artifact_id: UUID, artifact_instance: Union[SyncableArtifact, None] = None) -> None:
        """Register that a component belongs to an artifact."""
        if component_id not in cls._component_to_artifacts:
            cls._component_to_artifacts[component_id] = set()
        cls._component_to_artifacts[component_id].add(artifact_id)
        
        if artifact_id not in cls._artifact_components:
            cls._artifact_components[artifact_id] = set()
        cls._artifact_components[artifact_id].add(component_id)
        
        # Store the artifact instance for syncing
        if artifact_instance is not None:
            cls._artifact_instances[artifact_id] = artifact_instance
    
    @classmethod
    def unregister_component(cls, component_id: UUID, artifact_id: UUID) -> None:
        """Unregister that a component belongs to an artifact."""
        if component_id in cls._component_to_artifacts:
            cls._component_to_artifacts[component_id].discard(artifact_id)
            if not cls._component_to_artifacts[component_id]:
                del cls._component_to_artifacts[component_id]
        
        if artifact_id in cls._artifact_components:
            cls._artifact_components[artifact_id].discard(component_id)
            if not cls._artifact_components[artifact_id]:
                del cls._artifact_components[artifact_id]
                # Clean up artifact instance if no components left
                cls._artifact_instances.pop(artifact_id, None)
    
    @classmethod
    def get_artifact_ids(cls, component_id: UUID) -> set[UUID]:
        """Get the artifact IDs that contain the given component."""
        return cls._component_to_artifacts.get(component_id, set())
    
    @classmethod
    def get_component_ids(cls, artifact_id: UUID) -> set[UUID]:
        """Get the component IDs that belong to the given artifact."""
        return cls._artifact_components.get(artifact_id, set())
    
    @classmethod
    def is_registered(cls, component_id: UUID) -> bool:
        """Check if a component is registered with any artifact."""
        return component_id in cls._component_to_artifacts
    
    @classmethod
    def sync_artifact(cls, artifact_id: UUID) -> None:
        """Sync an artifact by its ID."""
        artifact_instance = cls._artifact_instances.get(artifact_id)
        if artifact_instance:
            artifact_instance._update()

    @classmethod
    async def sync_artifact_async(cls, artifact_id: UUID) -> None:
        """Sync an artifact by its ID."""
        artifact_instance = cls._artifact_instances.get(artifact_id)
        if artifact_instance:
            await artifact_instance._aupdate()