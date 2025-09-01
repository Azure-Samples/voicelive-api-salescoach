"""Tests for the graph_scenario_generator module."""

from unittest.mock import Mock, patch

from services.graph_scenario_generator import GraphScenarioGenerator


class TestGraphScenarioGenerator:
    """Test cases for GraphScenarioGenerator."""

    @patch("services.graph_scenario_generator.config")
    def test_initialization_missing_config(self, mock_config):
        """Test initialization with missing OpenAI configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_openai_endpoint": "",
            "azure_openai_api_key": "",
        }.get(key, "")

        generator = GraphScenarioGenerator()
        assert generator.openai_client is None

    @patch("services.graph_scenario_generator.AzureOpenAI")
    @patch("services.graph_scenario_generator.config")
    def test_initialization_success(self, mock_config, mock_azure_openai):
        """Test successful initialization with proper config."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_openai_endpoint": "https://test.openai.azure.com",
            "azure_openai_api_key": "test-key",
            "api_version": "2024-02-01",
        }.get(key, "test-value")

        generator = GraphScenarioGenerator()
        assert generator.openai_client is not None
        mock_azure_openai.assert_called_once()

    @patch("services.graph_scenario_generator.config")
    def test_initialization_exception(self, mock_config):
        """Test initialization with configuration exception."""
        mock_config.__getitem__.side_effect = Exception("Config error")

        generator = GraphScenarioGenerator()
        assert generator.openai_client is None

    @patch("services.graph_scenario_generator.config")
    def test_generate_scenario_from_graph_empty_data(self, mock_config):
        """Test scenario generation with empty graph data."""
        mock_config.__getitem__.side_effect = lambda key: {
            "model_deployment_name": "gpt-4",
        }.get(key, "test-value")

        generator = GraphScenarioGenerator()
        result = generator.generate_scenario_from_graph({})

        assert result["id"] == "graph-generated"
        assert result["name"] == "Your Personalized Sales Scenario"
        assert "generated_from_graph" in result
        assert result["generated_from_graph"] is True

    def test_generate_scenario_from_graph_with_meetings(self):
        """Test scenario generation with meeting data."""
        with patch("services.graph_scenario_generator.config") as mock_config:
            mock_config.__getitem__.side_effect = lambda key: {
                "model_deployment_name": "gpt-4",
            }.get(key, "test-value")

            graph_data = {
                "value": [
                    {
                        "subject": "Project Review",
                        "attendees": [
                            {"emailAddress": {"name": "John Doe"}},
                            {"emailAddress": {"name": "Jane Smith"}},
                        ],
                    },
                    {
                        "subject": "Sales Meeting",
                        "attendees": [
                            {"emailAddress": {"name": "Alice Johnson"}},
                        ],
                    },
                ]
            }

            generator = GraphScenarioGenerator()
            generator.openai_client = None  # Force use of fallback
            result = generator.generate_scenario_from_graph(graph_data)

            assert result["id"] == "graph-generated"
            assert result["name"] == "Your Personalized Sales Scenario"
            assert len(result["messages"]) == 1
            assert "content" in result["messages"][0]

    def test_format_meeting_list_empty(self):
        """Test formatting empty meeting list."""
        generator = GraphScenarioGenerator()
        result = generator._format_meeting_list([])
        assert result == ""

    def test_format_meeting_list_with_meetings(self):
        """Test formatting meeting list with data."""
        generator = GraphScenarioGenerator()
        meetings = [
            {"subject": "Team Standup", "attendees": ["Alice", "Bob"]},
            {
                "subject": "Client Call",
                "attendees": ["Charlie", "Diana", "Eve", "Frank"],
            },
        ]

        result = generator._format_meeting_list(meetings)
        expected = (
            "- Team Standup with Alice, Bob\n" "- Client Call with Charlie, Diana, Eve"
        )
        assert result == expected

    def test_create_graph_scenario_content_no_meetings(self):
        """Test scenario content creation with no meetings."""
        generator = GraphScenarioGenerator()
        result = generator._create_graph_scenario_content([])

        # Should return fallback content
        assert "Jordan Martinez" in result
        assert "TechCorp Solutions" in result

    def test_create_graph_scenario_content_no_openai_client(self):
        """Test scenario content creation with no OpenAI client."""
        generator = GraphScenarioGenerator()
        generator.openai_client = None

        meetings = [{"subject": "Test Meeting", "attendees": ["John"]}]
        result = generator._create_graph_scenario_content(meetings)

        # Should return fallback content
        assert "Jordan Martinez" in result
        assert "TechCorp Solutions" in result

    @patch("services.graph_scenario_generator.config")
    def test_create_graph_scenario_content_with_openai(self, mock_config):
        """Test scenario content creation with OpenAI client."""
        mock_config.__getitem__.side_effect = lambda key: {
            "model_deployment_name": "gpt-4",
        }.get(key, "test-value")

        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Generated scenario content"
        mock_client.chat.completions.create.return_value = mock_response

        generator = GraphScenarioGenerator()
        generator.openai_client = mock_client

        meetings = [{"subject": "Sales Call", "attendees": ["Alice", "Bob"]}]
        result = generator._create_graph_scenario_content(meetings)

        assert result == "Generated scenario content"
        mock_client.chat.completions.create.assert_called_once()

    @patch("services.graph_scenario_generator.config")
    def test_create_graph_scenario_content_openai_none_response(self, mock_config):
        """Test scenario content creation when OpenAI returns None content."""
        mock_config.__getitem__.side_effect = lambda key: {
            "model_deployment_name": "gpt-4",
        }.get(key, "test-value")

        # Mock OpenAI response with None content
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        generator = GraphScenarioGenerator()
        generator.openai_client = mock_client

        meetings = [{"subject": "Sales Call", "attendees": ["Alice"]}]
        result = generator._create_graph_scenario_content(meetings)

        assert result == ""

    def test_build_scenario_generation_prompt(self):
        """Test building the scenario generation prompt."""
        generator = GraphScenarioGenerator()
        meetings = [
            {"subject": "Quarterly Review", "attendees": ["Manager", "Team Lead"]},
            {"subject": "Product Demo", "attendees": ["Client", "Sales Rep"]},
        ]

        result = generator._build_scenario_generation_prompt(meetings)

        assert "Quarterly Review with Manager, Team Lead" in result
        assert "Product Demo with Client, Sales Rep" in result
        assert "role-play scenario" in result
        assert "Context" in result
        assert "Character" in result

    def test_get_fallback_scenario_content(self):
        """Test getting fallback scenario content."""
        generator = GraphScenarioGenerator()
        result = generator._get_fallback_scenario_content()

        assert "Jordan Martinez" in result
        assert "TechCorp Solutions" in result
        assert "BEHAVIORAL GUIDELINES" in result
        assert "YOUR CHARACTER PROFILE" in result
        assert "KEY CONCERNS TO RAISE" in result

    def test_generate_scenario_truncated_description(self):
        """Test scenario generation with long description that gets truncated."""
        with patch("services.graph_scenario_generator.config") as mock_config:
            mock_config.__getitem__.side_effect = lambda key: {
                "model_deployment_name": "gpt-4",
            }.get(key, "test-value")

            # Create a long scenario content that will be truncated
            generator = GraphScenarioGenerator()
            generator.openai_client = None  # Force use of fallback

            # Patch the fallback method to return long content
            long_content = (
                "This is a very long scenario description that should be truncated because it exceeds the 100 "
                "character limit set in the code. "
                * 3
            )
            generator._get_fallback_scenario_content = lambda: long_content

            result = generator.generate_scenario_from_graph({})

            # Description should be truncated to 100 characters + "..."
            assert len(result["description"]) <= 103
            assert result["description"].endswith("...")

    def test_generate_scenario_multiple_meetings_limit(self):
        """Test scenario generation limits meetings to first 3."""
        with patch("services.graph_scenario_generator.config") as mock_config:
            mock_config.__getitem__.side_effect = lambda key: {
                "model_deployment_name": "gpt-4",
            }.get(key, "test-value")

            # Create graph data with more than 3 meetings
            graph_data = {
                "value": [
                    {"subject": f"Meeting {i}", "attendees": []} for i in range(5)
                ]
            }

            generator = GraphScenarioGenerator()

            # Test the generate_scenario_from_graph method which processes meetings
            # We can test this by mocking the _create_graph_scenario_content method
            with patch.object(
                generator, "_create_graph_scenario_content"
            ) as mock_create:
                mock_create.return_value = "Test scenario content"

                generator.generate_scenario_from_graph(graph_data)

                # Verify the method was called with limited meetings
                assert mock_create.called
                called_meetings = mock_create.call_args[0][0]
                assert len(called_meetings) == 3
                assert called_meetings[0]["subject"] == "Meeting 0"
                assert called_meetings[1]["subject"] == "Meeting 1"
                assert called_meetings[2]["subject"] == "Meeting 2"

    def test_generate_scenario_attendees_limit(self):
        """Test scenario generation limits attendees to first 3 per meeting."""
        with patch("services.graph_scenario_generator.config") as mock_config:
            mock_config.__getitem__.side_effect = lambda key: {
                "model_deployment_name": "gpt-4",
            }.get(key, "test-value")

            # Create meeting with more than 3 attendees
            graph_data = {
                "value": [
                    {
                        "subject": "Big Meeting",
                        "attendees": [
                            {"emailAddress": {"name": f"Person {i}"}} for i in range(5)
                        ],
                    }
                ]
            }

            generator = GraphScenarioGenerator()

            # Test by mocking the _create_graph_scenario_content method
            with patch.object(
                generator, "_create_graph_scenario_content"
            ) as mock_create:
                mock_create.return_value = "Test scenario content"

                generator.generate_scenario_from_graph(graph_data)

                # Verify the method was called with limited attendees
                assert mock_create.called
                called_meetings = mock_create.call_args[0][0]
                assert len(called_meetings) == 1
                # Should only have first 3 attendees
                assert len(called_meetings[0]["attendees"]) == 3
                assert called_meetings[0]["attendees"] == [
                    "Person 0",
                    "Person 1",
                    "Person 2",
                ]
