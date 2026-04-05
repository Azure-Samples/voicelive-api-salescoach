"""Integration tests for Azure OpenAI - conversation analysis against real service.

These tests require deployed Azure resources and authenticate via DefaultAzureCredential.
Run with: pytest tests/integration/ -v
"""

import json
import os
import pytest

from tests.conftest import requires_azure


@pytest.fixture(scope="function")
def openai_client(azure_env):
    """Create a real Azure OpenAI client using deployed credentials."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    endpoint = azure_env["endpoint"]
    if not endpoint:
        pytest.skip("AZURE_OPENAI_ENDPOINT not set")

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if api_key and api_key.strip():
        return AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=endpoint,
            api_key=api_key,
        )
    else:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
        )


@requires_azure
class TestOpenAIIntegration:
    """Integration tests against real Azure OpenAI endpoint."""

    def test_chat_completion_basic(self, openai_client):
        """Test basic chat completion against the deployed model."""
        response = openai_client.chat.completions.create(
            model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Reply in one sentence."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            max_tokens=50,
        )
        assert response.choices[0].message.content is not None
        assert "4" in response.choices[0].message.content

    def test_chat_completion_structured_output(self, openai_client):
        """Test structured output (JSON schema) against the deployed model."""
        response = openai_client.chat.completions.create(
            model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an evaluator. Return a JSON evaluation.",
                },
                {
                    "role": "user",
                    "content": "Evaluate: 'Hello, I'd like to discuss our enterprise solution.'",
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "evaluation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "feedback": {"type": "string"},
                        },
                        "required": ["score", "feedback"],
                        "additionalProperties": False,
                    },
                },
            },
            max_tokens=200,
        )
        content = response.choices[0].message.content
        assert content is not None
        parsed = json.loads(content)
        assert "score" in parsed
        assert "feedback" in parsed
        assert isinstance(parsed["score"], int)

    def test_sales_evaluation_prompt(self, openai_client):
        """Test the full sales evaluation structured output matching the app's schema."""
        from src.services.analyzers import SalesEvaluation

        transcript = """
        User: Hi, I'm calling about your enterprise cloud solution. We're looking to migrate our infrastructure.
        Assistant: Great to hear! Tell me about your current setup and biggest pain points.
        User: We're running on-premises servers, and scaling is a nightmare. We need something more flexible.
        Assistant: I understand. Our solution offers auto-scaling and 99.9% uptime. What's your timeline?
        User: We'd like to start the migration within Q2 this year.
        """

        response = openai_client.beta.chat.completions.parse(
            model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert sales conversation evaluator. "
                    "Analyze the provided conversation and return a structured evaluation.",
                },
                {
                    "role": "user",
                    "content": f"Evaluate this sales conversation:\n{transcript}",
                },
            ],
            response_format=SalesEvaluation,
            max_tokens=500,
        )

        parsed = response.choices[0].message.parsed
        assert parsed is not None

        # Validate via Pydantic model attributes
        result = parsed.model_dump()

        # Validate structure matches the app's expected format
        assert "speaking_tone_style" in result
        assert "conversation_content" in result
        assert "overall_score" in result
        assert "strengths" in result
        assert "improvements" in result
        assert "specific_feedback" in result

        # Validate scores are reasonable
        assert 0 <= result["overall_score"] <= 100
        assert 0 <= result["speaking_tone_style"]["professional_tone"] <= 10
        assert isinstance(result["strengths"], list)
        assert isinstance(result["improvements"], list)

    def test_scenario_generation(self, openai_client):
        """Test scenario generation via OpenAI (GraphScenarioGenerator path)."""
        response = openai_client.chat.completions.create(
            model=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at creating realistic business role-play scenarios.",
                },
                {
                    "role": "user",
                    "content": "Generate a short sales role-play scenario for a cloud services pitch.",
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )
        content = response.choices[0].message.content
        assert content is not None
        assert len(content) > 50  # Should have meaningful content
