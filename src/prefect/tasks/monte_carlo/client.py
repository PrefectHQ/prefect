import json
import pendulum
import requests
from typing import Any, Dict, List

from prefect.utilities.logging import get_logger


class MonteCarloClient:
    def __init__(
        self,
        api_key_id: str,
        api_token: str,
    ) -> None:
        self.api_key_id = api_key_id
        self.api_token = api_token
        self.logger = get_logger()
        self._api_url = "https://api.getmontecarlo.com/graphql"

    def graphql(self, query: str, variables: dict = None) -> Dict[str, Any]:
        response = requests.post(
            url=self._api_url,
            json=dict(query=query, variables=variables),
            headers={
                "x-mcd-id": self.api_key_id,
                "x-mcd-token": self.api_token,
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        response = json.loads(response.text)
        self.logger.info("Response: %s", response)
        return response

    def get_warehouse_id_by_name(self, warehouse_name: str) -> str:
        response = self.graphql(
            query="""
                    {
                        getUser {
                            account {
                                warehouses {
                                    name
                                    uuid
                                }
                            }
                        }
                    }
                    """
        )
        warehouses = response["data"]["getUser"]["account"]["warehouses"]
        id_ = [w for w in warehouses if w["name"] == warehouse_name][0].get("uuid")
        return id_

    def get_resources(self) -> List[Dict[str, Any]]:
        response = self.graphql(
            query="""
                    query {
                        getResources {
                            name
                            type
                            id
                            uuid
                            isDefault
                            isUserProvided
                        }
                    }
                    """
        )
        return response["data"]["getResources"]

    def get_table_mcon(self, full_table_id: str, warehouse_name: str) -> str:
        response = self.graphql(
            query="""
                    query($dwh_id: UUID!, $full_table_id: String!) {
                        getTable(dwId: $dwh_id,
                            fullTableId: $full_table_id) {
                            mcon
                        }
                    }
                    """,
            variables=dict(
                dwh_id=self.get_warehouse_id_by_name(warehouse_name),
                full_table_id=full_table_id,
            ),
        )
        return response["data"]["getTable"]["mcon"]

    def get_node_mcon(self, object_id: str, object_type: str) -> str:
        response = self.graphql(
            query="""
                    query($object_id: String!, $object_type: String!) {
                        getLineageNode(objectId: $object_id,
                            objectType: $object_type) {
                            mcon
                        }
                    }
                    """,
            variables=dict(object_id=object_id, object_type=object_type),
        )
        mcon = response["data"]["getLineageNode"]["mcon"]
        self.logger.info("Object_id %s has the following MCON: %s", object_id, mcon)
        return mcon

    def create_or_update_tags_for_mcon(
        self, key: str, value: str, mcon: str
    ) -> Dict[str, Any]:
        response = self.graphql(
            query="""
                mutation($mcon_id: String!, $key: String!, $value: String!) {
                    createOrUpdateObjectProperty(mconId: $mcon_id,
                        propertyName: $key, propertyValue: $value) {
                        objectProperty {
                            id
                        }
                    }
                }
                """,
            variables=dict(mcon_id=mcon, key=key, value=value),
        )
        return response

    def create_or_update_lineage_node(
        self,
        node_name: str,
        object_id: str,
        object_type: str,
        resource_name: str,
    ):
        response = self.graphql(
            query="""
            mutation($node_name: String!, $object_id: String!, $object_type: String!, $resource_name: String!
            ) {
              createOrUpdateLineageNode(
                name: $node_name,
                objectId: $object_id,
                objectType: $object_type,
                resourceName: $resource_name,
              ){
                node{
                  nodeId
                  mcon
                }
              }
            }
            """,
            variables=dict(
                node_name=node_name,
                object_id=object_id,
                object_type=object_type,
                resource_name=resource_name,
            ),
        )
        return response["data"]["createOrUpdateLineageNode"]["node"]["mcon"]

    def create_or_update_lineage_node_with_tag(
        self,
        node_name: str,
        object_id: str,
        object_type: str,
        resource_name: str,
        metadata_key: str,
        metadata_value: str,
    ) -> str:
        response = self.graphql(
            query="""
            mutation($node_name: String!, $object_id: String!, $object_type: String!, $resource_name: String!, $metadata_key: String!, $metadata_value: String!
            ) {
              createOrUpdateLineageNode(
                name: $node_name,
                objectId: $object_id,
                objectType: $object_type,
                resourceName: $resource_name,
                properties: [{propertyName: $metadata_key, propertyValue: $metadata_value}]
              ){
                node{
                  nodeId
                  mcon
                }
              }
            }
            """,
            variables=dict(
                node_name=node_name,
                object_id=object_id,
                object_type=object_type,
                resource_name=resource_name,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            ),
        )
        return response["data"]["createOrUpdateLineageNode"]["node"]["mcon"]

    def create_or_update_resource(self, resource_name: str, resource_type: str):
        response = self.graphql(
            query="""
            mutation($resource_name: String!, $resource_type: String!) {
              createOrUpdateResource(
                isDefault: false,
                name: $resource_name,
                type: $resource_type,
              ) {
                resource {
                  uuid
                }
              }
            }
            """,
            variables=dict(resource_name=resource_name, resource_type=resource_type),
        )
        return response["data"]["createOrUpdateResource"]["resource"]["uuid"]

    def create_or_update_lineage_edge(
        self, source: dict, destination: dict, expire_at: str = None
    ):
        if expire_at is None:
            expire_at = pendulum.now().add(days=1).isoformat()

        response = self.graphql(
            query="""
                mutation($destination_object_id: String!, $destination_object_type: String!, 
                $destination_resource_name: String!, $source_object_id: String!, $source_object_type: String!,
                 $source_resource_name: String!, $expire_at: DateTime) {
                  createOrUpdateLineageEdge(
                    destination: {
                      objectId: $destination_object_id
                      objectType: $destination_object_type
                      resourceName: $destination_resource_name
                    }
                    source: {
                      objectId: $source_object_id
                      objectType: $source_object_type
                      resourceName: $source_resource_name
                    }
                    expireAt: $expire_at
                  ){
                    edge{
                      edgeId
                    }
                  }
                }
                """,
            variables=dict(
                destination_object_id=destination["object_id"],
                destination_object_type=destination["object_type"],
                destination_resource_name=destination["resource_name"],
                source_object_id=source["object_id"],
                source_object_type=source["object_type"],
                source_resource_name=source["resource_name"],
                expire_at=expire_at,
            ),
        )
        self.logger.info("Response of createOrUpdateLineageEdge %s", response)
        return response
