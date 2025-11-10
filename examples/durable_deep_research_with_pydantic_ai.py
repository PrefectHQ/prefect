# ---
# dependencies: ["prefect", "pydantic-ai[prefect]", "logfire"]
# keywords: ["ai", "agents", "pydantic-ai", "research", "llm", "durable-execution", "logfire", "observability"]
# ---
#
#
#
#
#
# This example demonstrates:
#
# ## Setup
#
# ```bash
# # or with pip:
# pip install "pydantic-ai[prefect]" logfire
# ```
#
# ```bash
# ```

from __future__ import annotations

import asyncio
from typing import Annotated

import logfire
from annotated_types import MaxLen
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, WebSearchTool, format_as_xml
from pydantic_ai.durable_exec.prefect import PrefectAgent, TaskConfig

from prefect import flow, task

#

logfire.configure()
logfire.instrument_pydantic_ai()


#


class WebSearchStep(BaseModel):
    """A single web search step in the research plan."""

    search_terms: str = Field(description="Search terms to use for this step")
    purpose: str = Field(description="What this search aims to discover or validate")


class DeepResearchPlan(BaseModel, **ConfigDict(use_attribute_docstrings=True)):
    """A structured plan for conducting deep research."""

    summary: str
    """High-level summary of the research approach."""

    web_search_steps: Annotated[list[WebSearchStep], MaxLen(5)]
    """List of web search steps to gather information (max 5 for efficiency)."""

    analysis_instructions: str
    """Instructions for synthesizing the search results into final insights."""


class ResearchFindings(BaseModel):
    """Structured research findings from the analysis agent."""

    executive_summary: str = Field(
        description="Concise executive summary of the research findings"
    )
    key_insights: list[str] = Field(
        description="Key insights discovered from the research",
        min_length=3,
        max_length=7,
    )
    supporting_evidence: list[str] = Field(
        description="Supporting evidence and sources for the insights",
        min_length=3,
        max_length=7,
    )
    recommendations: list[str] = Field(
        description="Actionable recommendations based on the findings",
        min_length=2,
        max_length=5,
    )

    def __str__(self) -> str:
        """Format research findings for display."""
        insights = "\n".join(
            f"  {i}. {insight}" for i, insight in enumerate(self.key_insights, 1)
        )
        evidence = "\n".join(
            f"  {i}. {item}" for i, item in enumerate(self.supporting_evidence, 1)
        )
        recommendations = "\n".join(
            f"  {i}. {rec}" for i, rec in enumerate(self.recommendations, 1)
        )

        return f"""
{"=" * 80}
RESEARCH FINDINGS
{"=" * 80}

📋 Executive Summary:
{self.executive_summary}

🔍 Key Insights:
{insights}

📚 Supporting Evidence:
{evidence}

💡 Recommendations:
{recommendations}
{"=" * 80}
"""


#


def create_planning_agent() -> PrefectAgent[None, DeepResearchPlan]:
    """Create a research planning agent with Prefect durability.

    This agent analyzes research queries and designs structured research plans.
    """
    agent = Agent(
        "openai:gpt-4o",
        name="research-planner",
        output_type=DeepResearchPlan,
        system_prompt=(
            "You are an expert research strategist. Analyze research queries and "
            "design comprehensive, structured research plans. Break down complex "
            "questions into specific, targeted web searches that will gather the "
            "most relevant information efficiently."
        ),
    )

    return PrefectAgent(
        agent,
        model_task_config=TaskConfig(
            retries=3,
            retry_delay_seconds=[1.0, 2.0, 4.0],
            timeout_seconds=60.0,
        ),
    )


def create_search_agent() -> PrefectAgent[None, str]:
    """Create a web search agent with Prefect durability.

    This agent performs web searches and summarizes results.
    """
    agent = Agent(
        "openai:gpt-4o-mini",
        name="web-searcher",
        builtin_tools=[WebSearchTool()],
        system_prompt=(
            "You are an expert web researcher. Perform thorough web searches "
            "and provide detailed, well-organized summaries of the results. "
            "Focus on factual information and cite sources when possible."
        ),
    )

    return PrefectAgent(
        agent,
        model_task_config=TaskConfig(
            retries=2,
            retry_delay_seconds=[1.0, 2.0],
            timeout_seconds=90.0,
        ),
        tool_task_config=TaskConfig(
            retries=3,
            retry_delay_seconds=[0.5, 1.0, 2.0],
        ),
    )


def create_analysis_agent() -> PrefectAgent[None, ResearchFindings]:
    """Create an analysis agent with Prefect durability.

    This agent synthesizes research findings into actionable insights.
    """
    agent = Agent(
        "openai:gpt-4o",
        name="research-analyst",
        output_type=ResearchFindings,
        system_prompt=(
            "You are an expert research analyst. Synthesize information from "
            "multiple sources into clear, actionable insights. Identify patterns, "
            "draw connections, and provide evidence-based recommendations. "
            "Always cite sources and distinguish between facts and interpretations."
        ),
    )

    @agent.tool_plain
    async def extra_search(query: str) -> str:
        """Perform an additional web search if more information is needed."""
        search_agent = create_search_agent()
        result = await search_agent.run(
            f"Search for: {query}. Provide a concise summary of findings."
        )
        return result.output

    return PrefectAgent(
        agent,
        model_task_config=TaskConfig(
            retries=3,
            retry_delay_seconds=[1.0, 2.0, 4.0],
            timeout_seconds=120.0,
        ),
        tool_task_config=TaskConfig(
            retries=2,
            retry_delay_seconds=[1.0, 2.0],
        ),
    )


#


@task(name="create-research-plan", retries=2)
async def create_research_plan(query: str) -> DeepResearchPlan:
    """Create a structured research plan for the given query.

    This task is automatically retried on failure and tracked in Prefect.
    """
    planner = create_planning_agent()
    result = await planner.run(f"Create a comprehensive research plan for: {query}")
    return result.output


@task(name="execute-web-search", retries=3)
async def execute_web_search(search_step: WebSearchStep) -> str:
    """Execute a single web search step.

    Prefect tracks each search independently, enabling parallel execution
    and individual retry logic.
    """
    searcher = create_search_agent()
    result = await searcher.run(
        f"Search for: {search_step.search_terms}\n"
        f"Purpose: {search_step.purpose}\n"
        f"Provide a detailed summary of relevant findings."
    )
    return result.output


@task(name="analyze-research-results", retries=2)
async def analyze_research_results(
    query: str, plan: DeepResearchPlan, search_results: list[str]
) -> ResearchFindings:
    """Analyze all research results and generate final insights.

    This task synthesizes information from all searches into structured findings.
    """
    analyzer = create_analysis_agent()

    research_context = format_as_xml(
        {
            "original_query": query,
            "research_plan": plan.summary,
            "search_results": [
                {
                    "search_terms": step.search_terms,
                    "purpose": step.purpose,
                    "findings": result,
                }
                for step, result in zip(plan.web_search_steps, search_results)
            ],
            "analysis_instructions": plan.analysis_instructions,
        }
    )

    result = await analyzer.run(
        f"Analyze the following research and generate comprehensive findings:\n\n{research_context}"
    )
    return result.output


#


@flow(name="durable-deep-research", log_prints=True)
async def conduct_deep_research(query: str) -> ResearchFindings:
    """Conduct comprehensive AI-powered research with durable execution.

    This flow demonstrates Prefect's durable execution capabilities:
    1. Each step is tracked and can be retried independently
    2. Parallel execution of web searches for efficiency
    3. Complete observability via Logfire instrumentation
    4. Automatic idempotency - failed runs can be retried safely
    5. All AI operations are resilient to transient failures

    Args:
        query: The research question or topic to investigate

    Returns:
        Structured research findings with insights and recommendations
    """
    print(f"🔬 Starting deep research on: {query}\n")

    print("📋 Creating research plan...")
    plan = await create_research_plan(query)
    print(f"✓ Plan created with {len(plan.web_search_steps)} search steps\n")

    print("🌐 Executing web searches in parallel...")
    search_tasks = [execute_web_search(step) for step in plan.web_search_steps]
    search_results = await asyncio.gather(*search_tasks)
    print(f"✓ Completed {len(search_results)} searches\n")

    print("🧠 Analyzing research results...")
    findings = await analyze_research_results(query, plan, search_results)
    print("✓ Analysis complete\n")

    print(findings)

    return findings


# ## Serve the Flow
#

if __name__ == "__main__":
    import os
    import sys

    required_keys = {
        "OPENAI_API_KEY": "OpenAI API key for GPT models",
    }

    missing_keys = [
        f"{key} ({desc})" for key, desc in required_keys.items() if not os.getenv(key)
    ]

    if missing_keys:
        print("❌ Error: Missing required environment variables:")
        for key in missing_keys:
            print(f"  - {key}")
        print("\nSet them with:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("\nOptional (for enhanced observability):")
        print("  export LOGFIRE_TOKEN='your-logfire-token'")
        sys.exit(1)

    # Serve the flow - this creates a deployment and runs a worker
    conduct_deep_research.serve(
        name="deep-research-deployment",
        tags=["ai", "pydantic-ai", "research", "durable-execution", "logfire"],
        parameters={
            "query": "What are the latest developments in durable execution frameworks for Python?"
        },
    )

#
#
# **Prefect UI:**
# 1. Navigate to http://localhost:4200
#
# **CLI:**
# ```bash
# ```
#
# ## Local Testing
#
# For quick local testing without deployment:
# ```python
# import asyncio
# ```

#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
