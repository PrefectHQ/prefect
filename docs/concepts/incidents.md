---
description: Incidents in Prefect Cloud help identify, rectify and document issues in mission-critical workflows.
tags:
    - UI
    - flow runs
    - triggers
    - Prefect Cloud
search:
  boost: 2
---

# Incidents<span class="badge cloud"><span class="badge beta"/>

## Overview

Incidents in Prefect Cloud is an advanced feature designed to optimize the management of workflow disruptions. It serves as a proactive tool for data-driven teams, helping them identify, rectify, and document issues in mission-critical workflows. This system enhances operational efficiency by automating the incident management process and providing a centralized platform for collaboration and compliance.

## What are incidents?

Incidents are formal declarations of disruptions to flow activity. Incidents vary in nature and severity, ranging from minor glitches to critical system failures. Prefect Cloud now enables users to effectively track and manage these incidents, ensuring minimal impact on operational continuity.

[Incidents in the Prefect Cloud UI](img/ui/incidents-dashboard.png)

## Why use incident management?

1. **Automated detection and reporting**: Incidents can be automatically identified based on specific triggers or manually reported by team members, facilitating prompt response.

2. **Collaborative problem-solving**: The platform fosters collaboration, allowing team members to share insights, discuss resolutions, and track contributions.

3. **Comprehensive impact assessment**: Users gain insights into the incident's influence on workflows, helping in prioritizing response efforts.

4. **Compliance with incident management processes**: Detailed documentation and reporting features support compliance with incident management systems.

5. **Enhanced operational transparency**: The system provides a transparent view of both ongoing and resolved incidents, promoting accountability and continuous improvement.

## How to use incident management in Prefect Cloud

### Creating an incident

1. **From the Incidents page**:
   - Click on the 'plus' button.
   - Fill in required fields and attach any relevant resources.

2. **From a flow Run, work Pool or block**:
   - Initiate an incident directly from a failed flow run, automatically linking it as a resource, by clicking on the menu button and selecting "Declare an incident".

3. **Via automation**:
   - Set up incident creation as an automated response to selected triggers.
     
### Incident automations

Automations can be used for triggering an incident and for selecting actions to take when an incident is triggered. For example, a work pool status change could trigger the declaration of an incident, or a critical level incident could trigger a notification action.

### Managing an incident

- **Monitor active incidents**: View real-time status, severity, and impact.
- **Adjust incident details**: Update status, severity, and other relevant information.
- **Collaborate**: Add comments and insights; these will display with user identifiers and timestamps.
- **Impact assessment**: Evaluate how the incident affects ongoing and future workflows.

### Resolving and documenting incidents

- **Resolution**: Update the incident status to reflect resolution steps taken.
- **Documentation**: Ensure all actions, comments, and changes are logged for future reference.

### Incident reporting

- Generate detailed reports summarizing the incident, actions taken, and resolution, suitable for compliance and retrospective analysis.


