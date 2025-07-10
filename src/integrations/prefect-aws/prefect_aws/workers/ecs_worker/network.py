"""
Network configuration management for ECS worker.
"""

from typing import Any, Optional


def load_network_configuration(
    vpc_id: Optional[str], configuration: Any, ec2_client: Any
) -> dict:
    """
    Load settings from a specific VPC or the default VPC and generate a task
    run request's network configuration.
    """
    vpc_message = "the default VPC" if not vpc_id else f"VPC with ID {vpc_id}"

    if not vpc_id:
        # Retrieve the default VPC
        describe = {"Filters": [{"Name": "isDefault", "Values": ["true"]}]}
    else:
        describe = {"VpcIds": [vpc_id]}

    vpcs = ec2_client.describe_vpcs(**describe)["Vpcs"]
    if not vpcs:
        help_message = (
            "Pass an explicit `vpc_id` or configure a default VPC."
            if not vpc_id
            else "Check that the VPC exists in the current region."
        )
        raise ValueError(
            f"Failed to find {vpc_message}. "
            "Network configuration cannot be inferred. " + help_message
        )

    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2_client.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]
    if not subnets:
        raise ValueError(
            f"Failed to find subnets for {vpc_message}. "
            "Network configuration cannot be inferred."
        )

    return {
        "awsvpcConfiguration": {
            "subnets": [s["SubnetId"] for s in subnets],
            "assignPublicIp": "ENABLED",
            "securityGroups": [],
        }
    }


def custom_network_configuration(
    vpc_id: str,
    network_configuration: dict,
    configuration: Any,
    ec2_client: Any,
) -> dict:
    """
    Load settings from a specific VPC or the default VPC and generate a task
    run request's network configuration.
    """
    vpc_message = f"VPC with ID {vpc_id}"

    vpcs = ec2_client.describe_vpcs(VpcIds=[vpc_id]).get("Vpcs")

    if not vpcs:
        raise ValueError(
            f"Failed to find {vpc_message}. "
            + "Network configuration cannot be inferred. "
            + "Pass an explicit `vpc_id`."
        )

    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2_client.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]

    if not subnets:
        raise ValueError(
            f"Failed to find subnets for {vpc_message}. "
            + "Network configuration cannot be inferred."
        )

    subnet_ids = [subnet["SubnetId"] for subnet in subnets]

    config_subnets = network_configuration.get("subnets", [])
    if not all(conf_sn in subnet_ids for conf_sn in config_subnets):
        raise ValueError(
            f"Subnets {config_subnets} not found within {vpc_message}."
            + "Please check that VPC is associated with supplied subnets."
        )

    return {"awsvpcConfiguration": network_configuration}
