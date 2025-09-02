# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""Analysis components for conversation and pronunciation assessment."""

import asyncio
import base64
import io
import json
import logging
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

import azure.cognitiveservices.speech as speechsdk  # pyright: ignore[reportMissingTypeStubs]
import yaml
from openai import AzureOpenAI

from src.config import config
from src.services.scenario_utils import determine_scenario_directory

logger = logging.getLogger(__name__)

# Constants
EVALUATION_FILE_SUFFIX = "*evaluation.prompt.yml"
EVALUATION_SUFFIX_REMOVAL = "-evaluation.prompt"
SCENARIO_DATA_DIR = "data/scenarios"
DOCKER_APP_PATH = "/app"

# Scoring constants
MAX_PROFESSIONAL_TONE_SCORE = 10
MAX_ACTIVE_LISTENING_SCORE = 10
MAX_ENGAGEMENT_QUALITY_SCORE = 10
MAX_NEEDS_ASSESSMENT_SCORE = 25
MAX_VALUE_PROPOSITION_SCORE = 25
MAX_OBJECTION_HANDLING_SCORE = 20
MAX_OVERALL_SCORE = 100
MAX_TONE_STYLE_SCORE = 30
MAX_CONTENT_SCORE = 70

# Audio processing constants
MIN_AUDIO_SIZE_BYTES = 48000
AUDIO_SAMPLE_RATE = 24000
AUDIO_CHANNELS = 1
AUDIO_SAMPLE_WIDTH = 2
AUDIO_BITS_PER_SAMPLE = 16

# Assessment constants
MAX_STRENGTHS_COUNT = 3
MAX_IMPROVEMENTS_COUNT = 3


class ConversationAnalyzer:
    """Analyzes sales conversations using Azure OpenAI."""

    def __init__(self, scenario_dir: Optional[Path] = None):
        """
        Initialize the conversation analyzer.

        Args:
            scenario_dir: Directory containing evaluation scenario files
        """
        self.scenario_dir = determine_scenario_directory(scenario_dir)
        self.evaluation_scenarios = self._load_evaluation_scenarios()
        self.openai_client = self._initialize_openai_client()

    def _load_evaluation_scenarios(self) -> Dict[str, Any]:
        """
        Load evaluation scenarios from YAML files.

        Returns:
            Dict[str, Any]: Dictionary of evaluation scenarios keyed by ID
        """
        scenarios: Dict[str, Any] = {}

        if not self.scenario_dir.exists():
            logger.warning("Scenarios directory not found: %s", self.scenario_dir)
            return scenarios

        for file in self.scenario_dir.glob(EVALUATION_FILE_SUFFIX):
            try:
                with open(file, encoding="utf-8") as f:
                    scenario = yaml.safe_load(f)
                    scenario_id = file.stem.replace(EVALUATION_SUFFIX_REMOVAL, "")
                    scenarios[scenario_id] = scenario
                    logger.info("Loaded evaluation scenario: %s", scenario_id)
            except Exception as e:
                logger.error("Error loading evaluation scenario %s: %s", file, e)

        logger.info("Total evaluation scenarios loaded: %s", len(scenarios))
        return scenarios

    def _initialize_openai_client(self) -> Optional[AzureOpenAI]:
        """
        Initialize the Azure OpenAI client.

        Returns:
            Optional[AzureOpenAI]: Initialized client or None if configuration missing
        """
        try:
            endpoint = config["azure_openai_endpoint"]
            api_key = config["azure_openai_api_key"]

            if not endpoint or not api_key:
                logger.error("Azure OpenAI endpoint or API key not configured")
                return None

            client = AzureOpenAI(
                api_version=config["api_version"],
                azure_endpoint=endpoint,
                api_key=api_key,
            )

            logger.info("ConversationAnalyzer initialized with endpoint: %s", endpoint)
            return client

        except Exception as e:
            logger.error("Failed to initialize OpenAI client: %s", e)
            return None

    async def analyze_conversation(self, scenario_id: str, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a conversation transcript.

        Args:
            scenario_id: The scenario identifier.
                         For AI generated scenario, use "graph_generated"
            transcript: The conversation transcript to analyze

        Returns:
            Optional[Dict[str, Any]]: Analysis results or None if analysis fails
        """
        logger.info("Starting conversation analysis for scenario: %s", scenario_id)

        evaluation_scenario = self.evaluation_scenarios.get(scenario_id)
        if not evaluation_scenario:
            logger.error("Evaluation scenario not found: %s", scenario_id)
            return None

        if not self.openai_client:
            logger.error("OpenAI client not configured")
            return None

        return await self._call_evaluation_model(evaluation_scenario, transcript)

    def _build_evaluation_prompt(self, scenario: Dict[str, Any], transcript: str) -> str:
        """Build the evaluation prompt."""
        base_prompt = scenario["messages"][0]["content"]
        return f"""{base_prompt}

        EVALUATION CRITERIA:

        **SPEAKING TONE & STYLE ({MAX_TONE_STYLE_SCORE} points total):**
        - professional_tone: 0-{MAX_PROFESSIONAL_TONE_SCORE} points for confident, consultative, appropriate business language
        - active_listening: 0-{MAX_ACTIVE_LISTENING_SCORE} points for acknowledging concerns and asking clarifying questions
        - engagement_quality: 0-{MAX_ENGAGEMENT_QUALITY_SCORE} points for encouraging dialogue and thoughtful responses

        **CONVERSATION CONTENT QUALITY ({MAX_CONTENT_SCORE} points total):**
        - needs_assessment: 0-{MAX_NEEDS_ASSESSMENT_SCORE} points for understanding customer challenges and goals
        - value_proposition: 0-{MAX_VALUE_PROPOSITION_SCORE} points for clear benefits with data/examples/reasoning
        - objection_handling: 0-{MAX_OBJECTION_HANDLING_SCORE} points for addressing concerns with constructive solutions

        Calculate overall_score as the sum of all individual scores (max {MAX_OVERALL_SCORE}).

        You are evaluating the conversation from perspective of the user (Starting the conversation)
        DO NOT rate the conversation of the 'assistant'!

        Provide maximum of {MAX_STRENGTHS_COUNT} strengths and {MAX_IMPROVEMENTS_COUNT} areas of improvement.

        CONVERSATION TO EVALUATE:
        {transcript}
        """

    async def _call_evaluation_model(self, scenario: Dict[str, Any], transcript: str) -> Optional[Dict[str, Any]]:
        """
        Call OpenAI with structured outputs for evaluation.

        Args:
            scenario: The evaluation scenario configuration
            transcript: The conversation transcript

        Returns:
            Optional[Dict[str, Any]]: Evaluation results or None if call fails
        """

        if not self.openai_client:
            logger.error("OpenAI client not configured")
            return None
        openai_client = self.openai_client

        try:
            evaluation_prompt = self._build_evaluation_prompt(scenario, transcript)

            completion = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai_client.chat.completions.create(
                    model=config["model_deployment_name"],
                    messages=self._build_evaluation_messages(evaluation_prompt),  # pyright: ignore[reportArgumentType]
                    response_format=self._get_response_format(),  # pyright: ignore[reportArgumentType]
                ),
            )

            if completion.choices[0].message.content:
                evaluation_json = json.loads(completion.choices[0].message.content)
                return self._process_evaluation_result(evaluation_json)

            logger.error("No content received from OpenAI")
            return None

        except Exception as e:
            logger.error("Error in evaluation model: %s", e)
            return None

    def _build_evaluation_messages(self, evaluation_prompt: str) -> List[Dict[str, str]]:
        """Build the messages for the evaluation API call."""
        return [
            {
                "role": "system",
                "content": "You are an expert sales conversation evaluator. "
                "Analyze the provided conversation and return a structured evaluation.",
            },
            {"role": "user", "content": evaluation_prompt},
        ]

    def _get_response_format(self) -> Dict[str, Any]:
        """Get the structured response format for OpenAI."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "sales_evaluation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "speaking_tone_style": {
                            "type": "object",
                            "properties": {
                                "professional_tone": {"type": "integer"},
                                "active_listening": {"type": "integer"},
                                "engagement_quality": {"type": "integer"},
                                "total": {"type": "integer"},
                            },
                            "required": [
                                "professional_tone",
                                "active_listening",
                                "engagement_quality",
                                "total",
                            ],
                            "additionalProperties": False,
                        },
                        "conversation_content": {
                            "type": "object",
                            "properties": {
                                "needs_assessment": {"type": "integer"},
                                "value_proposition": {"type": "integer"},
                                "objection_handling": {"type": "integer"},
                                "total": {"type": "integer"},
                            },
                            "required": [
                                "needs_assessment",
                                "value_proposition",
                                "objection_handling",
                                "total",
                            ],
                            "additionalProperties": False,
                        },
                        "overall_score": {"type": "integer"},
                        "strengths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "improvements": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "specific_feedback": {"type": "string"},
                    },
                    "required": [
                        "speaking_tone_style",
                        "conversation_content",
                        "overall_score",
                        "strengths",
                        "improvements",
                        "specific_feedback",
                    ],
                    "additionalProperties": False,
                },
            },
        }

    def _process_evaluation_result(self, evaluation_json: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate evaluation results."""
        evaluation_json["speaking_tone_style"]["total"] = sum(
            [
                evaluation_json["speaking_tone_style"]["professional_tone"],
                evaluation_json["speaking_tone_style"]["active_listening"],
                evaluation_json["speaking_tone_style"]["engagement_quality"],
            ]
        )

        evaluation_json["conversation_content"]["total"] = sum(
            [
                evaluation_json["conversation_content"]["needs_assessment"],
                evaluation_json["conversation_content"]["value_proposition"],
                evaluation_json["conversation_content"]["objection_handling"],
            ]
        )

        logger.info("Evaluation processed with score: %s", evaluation_json.get("overall_score"))
        return evaluation_json


class PronunciationAssessor:
    """Assesses pronunciation using Azure Speech Services."""

    def __init__(self):
        """Initialize the pronunciation assessor."""
        self.speech_key = config["azure_speech_key"]
        self.speech_region = config["azure_speech_region"]

    def _create_wav_audio(self, audio_bytes: bytearray) -> bytes:
        """Create WAV format audio from raw PCM bytes."""
        with io.BytesIO() as wav_buffer:
            wav_file: wave.Wave_write = wave.open(wav_buffer, "wb")  # type: ignore
            with wav_file:
                wav_file.setnchannels(AUDIO_CHANNELS)
                wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH)
                wav_file.setframerate(AUDIO_SAMPLE_RATE)
                wav_file.writeframes(audio_bytes)

            wav_buffer.seek(0)
            return wav_buffer.read()

    def _log_assessment_info(self, wav_audio: bytes, reference_text: Optional[str]) -> None:
        """Log information about the assessment being performed."""
        logger.info("Starting pronunciation assessment with audio size: %s bytes", len(wav_audio))
        logger.info("Reference text: %s", reference_text or "None")
        logger.info("Speech key configured: %s", "Yes" if self.speech_key else "No")
        logger.info("Speech region: %s", self.speech_region)

    def _create_speech_config(self) -> speechsdk.SpeechConfig:
        """Create speech configuration."""
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        speech_config.speech_recognition_language = config["azure_speech_language"]
        return speech_config

    def _create_pronunciation_config(self, reference_text: Optional[str]) -> speechsdk.PronunciationAssessmentConfig:
        """Create pronunciation assessment configuration."""
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text or "",
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation_config.enable_prosody_assessment()
        return pronunciation_config

    def _create_audio_config(self, wav_audio: bytes) -> speechsdk.audio.AudioConfig:
        """Create audio configuration from WAV data."""
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=AUDIO_SAMPLE_RATE,
            bits_per_sample=AUDIO_BITS_PER_SAMPLE,
            channels=AUDIO_CHANNELS,
            wave_stream_format=speechsdk.audio.AudioStreamWaveFormat.PCM,
        )

        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
        push_stream.write(wav_audio)
        push_stream.close()

        return speechsdk.audio.AudioConfig(stream=push_stream)

    def _build_assessment_result(
        self,
        pronunciation_result: speechsdk.PronunciationAssessmentResult,
        result: speechsdk.SpeechRecognitionResult,
    ) -> Dict[str, Any]:
        """Build the final assessment result."""
        return {
            "accuracy_score": pronunciation_result.accuracy_score,
            "fluency_score": pronunciation_result.fluency_score,
            "completeness_score": pronunciation_result.completeness_score,
            "prosody_score": getattr(pronunciation_result, "prosody_score", None),
            "pronunciation_score": pronunciation_result.pronunciation_score,
            "words": self._extract_word_details(result),
        }

    async def assess_pronunciation(
        self, audio_data: List[Dict[str, Any]], reference_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Assess pronunciation of audio data.

        Args:
            audio_data: List of audio chunks with metadata
            reference_text: Optional reference text for comparison

        Returns:
            Optional[Dict[str, Any]]: Pronunciation assessment results or None if assessment fails
        """
        if not self.speech_key:
            logger.error("Azure Speech key not configured")
            return None

        try:
            combined_audio = await self._prepare_audio_data(audio_data)
            if not combined_audio:
                logger.error("No audio data to assess")
                return None

            logger.info("Combined audio size: %s bytes", len(combined_audio))

            if len(combined_audio) < MIN_AUDIO_SIZE_BYTES:
                logger.warning("Audio might be too short: %s bytes", len(combined_audio))

            wav_audio = self._create_wav_audio(combined_audio)
            return await self._perform_assessment(wav_audio, reference_text)

        except Exception as e:
            logger.error("Error in pronunciation assessment: %s", e)
            return None

    async def _prepare_audio_data(self, audio_data: List[Dict[str, Any]]) -> bytearray:
        """Prepare and combine audio chunks."""
        combined_audio = bytearray()

        for chunk in audio_data:
            if chunk.get("type") == "user":
                try:
                    audio_bytes = base64.b64decode(chunk["data"])
                    combined_audio.extend(audio_bytes)
                except Exception as e:
                    logger.error("Error decoding audio chunk: %s", e)

        return combined_audio

    async def _perform_assessment(self, wav_audio: bytes, reference_text: Optional[str]) -> Optional[Dict[str, Any]]:
        """Perform the actual pronunciation assessment."""
        self._log_assessment_info(wav_audio, reference_text)

        speech_config = self._create_speech_config()
        pronunciation_config = self._create_pronunciation_config(reference_text)
        audio_config = self._create_audio_config(wav_audio)

        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
            language=config["azure_speech_language"],
        )
        pronunciation_config.apply_to(speech_recognizer)

        result = await asyncio.get_event_loop().run_in_executor(None, speech_recognizer.recognize_once)

        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        return self._build_assessment_result(pronunciation_result, result)

    def _extract_word_details(self, result: speechsdk.SpeechRecognitionResult) -> List[Dict[str, Any]]:
        """Extract word-level pronunciation details."""
        try:
            json_result = json.loads(
                result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult,
                    "{}",
                )  # pyright: ignore[reportUnknownMemberType]  # pyright: ignore[reportUnknownArgumentType]
            )

            words: List[Dict[str, Any]] = []
            if "NBest" in json_result and json_result["NBest"]:
                for word_info in json_result["NBest"][0].get("Words", []):
                    words.append(
                        {
                            "word": word_info.get("Word", ""),
                            "accuracy": word_info.get("PronunciationAssessment", {}).get("AccuracyScore", 0),
                            "error_type": word_info.get("PronunciationAssessment", {}).get("ErrorType", "None"),
                        }
                    )

            return words
        except Exception as e:
            logger.error("Error extracting word details: %s", e)
            return []
