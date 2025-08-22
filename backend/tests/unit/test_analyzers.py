"""Tests for analyzer classes."""

import pytest
from unittest.mock import Mock, patch
import tempfile
import yaml
from pathlib import Path
import json
import base64

from analyzers import ConversationAnalyzer, PronunciationAssessor


class TestConversationAnalyzer:
    """Test conversation analyzer functionality."""

    def test_conversation_analyzer_initialization(self):
        """Test analyzer initialization with no scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = Path(temp_dir) / "nonexistent"
            analyzer = ConversationAnalyzer(scenario_dir=non_existent_path)
            assert len(analyzer.evaluation_scenarios) == 0

    def test_load_evaluation_scenarios(self):
        """Test loading evaluation scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            scenario_dir = Path(temp_dir)

            # Create a test evaluation scenario file
            scenario_data = {
                "name": "Test Evaluation",
                "messages": [{"content": "Evaluate this conversation"}],
            }

            scenario_file = scenario_dir / "test-scenario-evaluation.prompt.yml"
            with open(scenario_file, "w") as f:
                yaml.safe_dump(scenario_data, f)

            analyzer = ConversationAnalyzer(scenario_dir=scenario_dir)
            assert len(analyzer.evaluation_scenarios) == 1
            assert "test-scenario" in analyzer.evaluation_scenarios

    @patch("analyzers.config")
    def test_initialize_openai_client_missing_config(self, mock_config):
        """Test OpenAI client initialization with missing config."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_openai_endpoint": "",
            "azure_openai_api_key": "",
        }.get(key, "")

        analyzer = ConversationAnalyzer()
        assert analyzer.openai_client is None

    @patch("analyzers.AzureOpenAI")
    @patch("analyzers.config")
    def test_initialize_openai_client_success(self, mock_config, mock_azure_openai):
        """Test successful OpenAI client initialization."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_openai_endpoint": "https://test.openai.azure.com",
            "azure_openai_api_key": "test-key",
        }.get(key, "")

        analyzer = ConversationAnalyzer()
        assert analyzer.openai_client is not None
        mock_azure_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_conversation_missing_scenario(self):
        """Test analyzing conversation with missing scenario."""
        analyzer = ConversationAnalyzer()
        analyzer.evaluation_scenarios = {}

        result = await analyzer.analyze_conversation("nonexistent", "test transcript")
        assert result is None

    def test_build_evaluation_prompt(self):
        """Test building evaluation prompt."""
        analyzer = ConversationAnalyzer()
        scenario = {"messages": [{"content": "Base evaluation prompt"}]}
        transcript = "Test conversation"

        prompt = analyzer._build_evaluation_prompt(scenario, transcript)
        assert "Base evaluation prompt" in prompt
        assert "Test conversation" in prompt
        assert "EVALUATION CRITERIA" in prompt
        assert "SPEAKING TONE & STYLE" in prompt

    def test_get_response_format(self):
        """Test getting response format for structured output."""
        analyzer = ConversationAnalyzer()
        format_def = analyzer._get_response_format()

        assert format_def["type"] == "json_schema"
        assert "sales_evaluation" in format_def["json_schema"]["name"]

        schema = format_def["json_schema"]["schema"]
        assert "speaking_tone_style" in schema["properties"]
        assert "conversation_content" in schema["properties"]
        assert "overall_score" in schema["properties"]

    def test_process_evaluation_result(self):
        """Test processing evaluation results."""
        analyzer = ConversationAnalyzer()

        evaluation_json = {
            "speaking_tone_style": {
                "professional_tone": 8,
                "active_listening": 7,
                "engagement_quality": 9,
                "total": 0,  # Will be recalculated
            },
            "conversation_content": {
                "needs_assessment": 20,
                "value_proposition": 18,
                "objection_handling": 15,
                "total": 0,  # Will be recalculated
            },
            "overall_score": 77,
            "strengths": ["Good engagement"],
            "improvements": ["Better needs assessment"],
            "specific_feedback": "Overall good performance",
        }

        result = analyzer._process_evaluation_result(evaluation_json)

        assert result["speaking_tone_style"]["total"] == 24
        assert result["conversation_content"]["total"] == 53
        assert result["overall_score"] == 77


class TestPronunciationAssessor:
    """Test pronunciation assessor functionality."""

    def test_pronunciation_assessor_initialization(self):
        """Test assessor initialization."""
        assessor = PronunciationAssessor()
        # Test that it initializes with config values
        assert hasattr(assessor, "speech_key")
        assert hasattr(assessor, "speech_region")

    @pytest.mark.asyncio
    async def test_assess_pronunciation_no_speech_key(self):
        """Test pronunciation assessment with no speech key configured."""
        assessor = PronunciationAssessor()
        assessor.speech_key = None

        result = await assessor.assess_pronunciation([], "test text")
        assert result is None

    @pytest.mark.asyncio
    async def test_prepare_audio_data_empty_list(self):
        """Test preparing audio data with empty list."""
        assessor = PronunciationAssessor()
        result = await assessor._prepare_audio_data([])
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_prepare_audio_data_with_user_chunks(self):
        """Test preparing audio data with user chunks."""
        assessor = PronunciationAssessor()

        # Create test audio data
        test_audio = b"test audio data"
        encoded_audio = base64.b64encode(test_audio).decode("utf-8")

        audio_data = [
            {"type": "user", "data": encoded_audio},
            {"type": "assistant", "data": "should be ignored"},
        ]

        result = await assessor._prepare_audio_data(audio_data)
        assert len(result) > 0
        assert test_audio in result

    def test_create_wav_audio(self):
        """Test creating WAV audio from raw bytes."""
        assessor = PronunciationAssessor()
        test_audio = bytearray(b"test audio data" * 100)  # Make it longer

        wav_audio = assessor._create_wav_audio(test_audio)
        assert isinstance(wav_audio, bytes)
        assert len(wav_audio) > len(test_audio)  # WAV header adds overhead

    def test_extract_word_details_empty_result(self):
        """Test extracting word details from empty result."""
        assessor = PronunciationAssessor()

        # Mock result object
        mock_result = Mock()
        mock_result.properties.get.return_value = "{}"

        words = assessor._extract_word_details(mock_result)
        assert words == []

    def test_extract_word_details_with_words(self):
        """Test extracting word details with actual words."""
        assessor = PronunciationAssessor()

        # Mock result with word data
        mock_result = Mock()
        test_response = {
            "NBest": [
                {
                    "Words": [
                        {
                            "Word": "hello",
                            "PronunciationAssessment": {
                                "AccuracyScore": 85,
                                "ErrorType": "None",
                            },
                        },
                        {
                            "Word": "world",
                            "PronunciationAssessment": {
                                "AccuracyScore": 90,
                                "ErrorType": "None",
                            },
                        },
                    ]
                }
            ]
        }
        mock_result.properties.get.return_value = json.dumps(test_response)

        words = assessor._extract_word_details(mock_result)

        assert len(words) == 2
        assert words[0]["word"] == "hello"
        assert words[0]["accuracy"] == 85
        assert words[1]["word"] == "world"
        assert words[1]["accuracy"] == 90
