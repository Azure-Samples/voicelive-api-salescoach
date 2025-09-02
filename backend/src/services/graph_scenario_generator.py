# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""Graph API scenario generation service."""

import logging
from typing import Dict, Any, Optional, List

from openai import AzureOpenAI

from src.config import config

logger = logging.getLogger(__name__)


class GraphScenarioGenerator:
    """Generates training scenarios based on Microsoft Graph API data."""

    def __init__(self):
        """Initialize the Graph scenario generator."""
        self.openai_client = self._initialize_openai_client()

    def _initialize_openai_client(self) -> Optional[AzureOpenAI]:
        """Initialize the Azure OpenAI client for scenario generation."""
        try:
            endpoint = config["azure_openai_endpoint"]
            api_key = config["azure_openai_api_key"]

            if not endpoint or not api_key:
                logger.warning("Azure OpenAI not configured for scenario generation")
                return None

            return AzureOpenAI(
                api_version=config["api_version"],
                azure_endpoint=endpoint,
                api_key=api_key,
            )
        except Exception as e:
            logger.error("Failed to initialize OpenAI client for scenarios: %s", e)
            return None

    def generate_scenario_from_graph(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a scenario based on Microsoft Graph API data.

        Args:
            graph_data: The Graph API response data

        Returns:
            Dict[str, Any]: Generated scenario
        """
        meetings: List[Dict[str, Any]] = []
        if "value" in graph_data:
            for event in graph_data["value"][:3]:
                subject = event.get("subject", "Meeting")
                attendees = [attendee["emailAddress"]["name"] for attendee in event.get("attendees", [])[:3]]
                meetings.append({"subject": subject, "attendees": attendees})

        scenario_content = self._create_graph_scenario_content(meetings)

        first_sentence = scenario_content.split(".")[0] + "."
        if len(first_sentence) > 100:
            first_sentence = first_sentence[:100] + "..."

        return {
            "id": "graph-generated",
            "name": "Your Personalized Sales Scenario",
            "description": first_sentence,
            "messages": [{"content": scenario_content}],
            "model": config["model_deployment_name"],
            "modelParameters": {"temperature": 0.7, "max_tokens": 2000},
            "generated_from_graph": True,
        }

    def _format_meeting_list(self, meetings: List[Dict[str, Any]]) -> str:
        """Format the list of meetings for display."""
        return "\n".join(f"- {meeting['subject']} with {', '.join(meeting['attendees'][:3])}" for meeting in meetings)

    def _create_graph_scenario_content(self, meetings: List[Dict[str, Any]]) -> str:
        """Create scenario content based on meetings using OpenAI."""
        if not meetings:
            return self._get_fallback_scenario_content()

        if not self.openai_client:
            logger.warning("OpenAI client not available, using fallback scenario")
            return self._get_fallback_scenario_content()

        prompt = self._build_scenario_generation_prompt(meetings)

        response = self.openai_client.chat.completions.create(
            model=config["model_deployment_name"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert at creating realistic business role-play scenarios for sales training. "
                        "Generate engaging, professional scenarios that help salespeople prepare for real meetings."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
        )

        content = response.choices[0].message.content
        generated_content = content.strip() if content is not None else ""
        return generated_content

    def _build_scenario_generation_prompt(self, meetings: List[Dict[str, Any]]) -> str:
        """Build the prompt for OpenAI scenario generation."""
        return (
            "Generate a role-play scenario to help a salesperson prepare for their upcoming client meetings. "
            "Based on their calendar, the following meetings are scheduled:\n\n"
            f"{self._format_meeting_list(meetings)}\n\n"
            "Create a realistic sales practice scenario for an upcoming customer meeting using the following "
            "structure:\n\n"
            "1. **Context**: Start with a quick summary.\n"
            "2. **Character**: Define the person the trainee will interact with (name, title, company background). "
            "The company description should include industry, size, and strategic focus.\n"
            "3. **Behavioral Guidelines (Act Human)**: Outline how the character should behave in conversation "
            "(e.g., open, skeptical, budget-conscious, visionary).\n"
            "4. **Character Profile**: Provide background experience and current responsibilities that shape the "
            "character's perspective.\n"
            "5. **Key Concerns**: List 2–3 specific business concerns, objections, or challenges the character should "
            "raise during the conversation. These should be realistic for their role and company context.\n"
            "6. **Instruction**: End by telling the AI to roleplay as this character, responding naturally and "
            "professionally, raising concerns where relevant.\n\n"
            "**Example output:**\n\n"
            "Discovery call with ContosoCare on SaaS platform.\n\n"
            "You are **Sarah Lee, Director of Patient Experience at ContosoCare**, a healthcare provider focused on "
            "delivering modern, patient-centered digital solutions while navigating strict compliance requirements.\n\n"
            "**BEHAVIORAL GUIDELINES (Act Human):**\n\n"
            "* Speak conversationally, avoid jargon overload\n"
            "* Show interest in how technology solves real problems\n"
            "* Ask open-ended questions about business outcomes\n\n"
            "**YOUR CHARACTER PROFILE:**\n\n"
            "* 12 years in healthcare operations and patient engagement\n"
            "* Recently led ContosoCare's shift to hybrid care models (in-person + telehealth)\n"
            "* Practical, budget-aware, but open to innovation if it improves patient satisfaction\n\n"
            "**KEY CONCERNS TO RAISE:**\n\n"
            "1. How does your platform handle HIPAA/GDPR compliance without slowing workflows?\n"
            "2. Our clinicians already struggle with multiple tools — how will this integrate with existing EMR "
            "systems?\n"
            "3. Budgets are tight — what ROI can we realistically expect in the first year?\n\n"
            "**Respond naturally as Sarah Lee would, maintaining professional tone while expressing genuine business "
            "concerns.**\n\n"
            "Directly start with the summary (No 'Context:')\n"
        )

    def _get_fallback_scenario_content(self) -> str:
        """Fallback scenario content when generation fails."""
        return (
            "You are Jordan Martinez, Operations Director at TechCorp Solutions, a mid-size technology "
            "consulting firm with 200+ employees. You're evaluating new software solutions to improve team "
            "collaboration and productivity.\n\n"
            "BEHAVIORAL GUIDELINES (Act Human):\n"
            "- Show genuine interest but maintain professional skepticism\n"
            "- Ask clarifying questions when information seems unclear\n"
            '- Take natural pauses to "think" before responding to complex proposals\n\n'
            "YOUR CHARACTER PROFILE:\n"
            "- 10+ years in operations and technology management\n"
            "- Results-driven but relationship-focused\n"
            "- Currently managing remote and hybrid teams\n\n"
            "KEY CONCERNS TO RAISE:\n"
            "1. Integration complexity with existing systems and workflows\n"
            "2. Change management and user adoption challenges\n"
            "3. Total cost of ownership including training and support\n\n"
            "Respond naturally as Jordan would, maintaining professional tone while expressing genuine business "
            "concerns about technology investments and team productivity.\n"
        )
