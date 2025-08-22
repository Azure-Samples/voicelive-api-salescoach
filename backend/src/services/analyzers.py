"""Analysis components for conversation and pronunciation assessment."""

import asyncio
import base64
import io
import json
import logging
import os
import wave
from pathlib import Path
from typing import Dict, Any, Optional, List

import azure.cognitiveservices.speech as speechsdk
import yaml
from openai import AzureOpenAI

from config import config

logger = logging.getLogger(__name__)


class ConversationAnalyzer:
    """Analyzes sales conversations using Azure OpenAI."""

    def __init__(self, scenario_dir: Path = None):
        """
        Initialize the conversation analyzer.

        Args:
            scenario_dir: Directory containing evaluation scenario files
        """
        if scenario_dir is None:
            docker_path = Path("/app/data/scenarios")
            if docker_path.exists():
                self.scenario_dir = docker_path
            else:
                self.scenario_dir = (
                    Path(__file__).parent.parent.parent.parent / "data" / "scenarios"
                )
        else:
            self.scenario_dir = scenario_dir
        self.evaluation_scenarios = self._load_evaluation_scenarios()
        self.openai_client = self._initialize_openai_client()

    def _load_evaluation_scenarios(self) -> Dict[str, Any]:
        """
        Load evaluation scenarios from YAML files.

        Returns:
            Dict[str, Any]: Dictionary of evaluation scenarios keyed by ID
        """
        scenarios = {}

        if not self.scenario_dir.exists():
            logger.warning(f"Scenarios directory not found: {self.scenario_dir}")
            return scenarios

        for file in self.scenario_dir.glob("*evaluation.prompt.yml"):
            try:
                with open(file) as f:
                    scenario = yaml.safe_load(f)
                    scenario_id = file.stem.replace("-evaluation.prompt", "")
                    scenarios[scenario_id] = scenario
                    logger.info(f"Loaded evaluation scenario: {scenario_id}")
            except Exception as e:
                logger.error(f"Error loading evaluation scenario {file}: {e}")

        logger.info(f"Total evaluation scenarios loaded: {len(scenarios)}")
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
                api_version="2024-12-01-preview",
                azure_endpoint=endpoint,
                api_key=api_key,
            )

            logger.info(f"ConversationAnalyzer initialized with endpoint: {endpoint}")
            return client

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return None

    async def analyze_conversation(
        self, scenario_id: str, transcript: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a conversation transcript.

        Args:
            scenario_id: The scenario identifier
            transcript: The conversation transcript to analyze

        Returns:
            Optional[Dict[str, Any]]: Analysis results or None if analysis fails
        """
        logger.info(f"Starting conversation analysis for scenario: {scenario_id}")

        evaluation_scenario = self.evaluation_scenarios.get(scenario_id)
        if not evaluation_scenario:
            logger.error(f"Evaluation scenario not found: {scenario_id}")
            return None

        if not self.openai_client:
            logger.error("OpenAI client not configured")
            return None

        return await self._call_evaluation_model(evaluation_scenario, transcript)

    async def _call_evaluation_model(
        self, scenario: Dict[str, Any], transcript: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call OpenAI with structured outputs for evaluation.

        Args:
            scenario: The evaluation scenario configuration
            transcript: The conversation transcript

        Returns:
            Optional[Dict[str, Any]]: Evaluation results or None if call fails
        """
        try:
            evaluation_prompt = self._build_evaluation_prompt(scenario, transcript)

            completion = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert sales conversation evaluator. "
                            "Analyze the provided conversation and return a structured evaluation.",
                        },
                        {"role": "user", "content": evaluation_prompt},
                    ],
                    response_format=self._get_response_format(),
                ),
            )

            if completion.choices[0].message.content:
                evaluation_json = json.loads(completion.choices[0].message.content)
                return self._process_evaluation_result(evaluation_json)

            logger.error("No content received from OpenAI")
            return None

        except Exception as e:
            logger.error(f"Error in evaluation model: {e}")
            return None

    def _build_evaluation_prompt(
        self, scenario: Dict[str, Any], transcript: str
    ) -> str:
        """Build the evaluation prompt."""
        base_prompt = scenario["messages"][0]["content"]
        return f"""{base_prompt}

        EVALUATION CRITERIA:

        **SPEAKING TONE & STYLE (30 points total):**
        - professional_tone: 0-10 points for confident, consultative, appropriate business language
        - active_listening: 0-10 points for acknowledging concerns and asking clarifying questions
        - engagement_quality: 0-10 points for encouraging dialogue and thoughtful responses

        **CONVERSATION CONTENT QUALITY (70 points total):**
        - needs_assessment: 0-25 points for understanding customer challenges and goals
        - value_proposition: 0-25 points for clear benefits with data/examples/reasoning
        - objection_handling: 0-20 points for addressing concerns with constructive solutions

        Calculate overall_score as the sum of all individual scores (max 100).

        You are evaluating the conversation from perspective of the user (Starting the conversation)
        DO NOT rate the conversation of the 'assistant'!


        Provide maximum of 3 strengths and 3 areas of improvement.


        CONVERSATION TO EVALUATE:
        {transcript}
        """

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

    def _process_evaluation_result(
        self, evaluation_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process and validate evaluation results."""
        # Recalculate totals to ensure accuracy
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

        logger.info(
            f"Evaluation processed with score: {evaluation_json.get('overall_score')}"
        )
        return evaluation_json


class PronunciationAssessor:
    """Assesses pronunciation using Azure Speech Services."""

    def __init__(self):
        """Initialize the pronunciation assessor."""
        self.speech_key = config["azure_speech_key"]
        self.speech_region = config["azure_speech_region"]
        self._is_docker = self._detect_docker_environment()
        self._platform_available = None  # Will be set on first use
        
    def _detect_docker_environment(self) -> bool:
        """Detect if running in a Docker container."""
        try:
            # Check for Docker-specific indicators
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read() or 'containerd' in f.read()
        except (FileNotFoundError, PermissionError):
            # Fallback: check for other Docker indicators
            return (
                os.path.exists('/.dockerenv') or 
                os.environ.get('DOCKER_CONTAINER') == 'true'
            )
    
    def _create_mock_assessment(self) -> Dict[str, Any]:
        """Create a mock pronunciation assessment when Speech SDK is unavailable."""
        return {
            "accuracy_score": 85.0,
            "fluency_score": 80.0, 
            "completeness_score": 90.0,
            "prosody_score": 75.0,
            "pronunciation_score": 82.5,
            "words": [],
            "mock_data": True,
            "reason": "Speech SDK unavailable in Docker environment"
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
            # Prepare audio data
            combined_audio = await self._prepare_audio_data(audio_data)
            if not combined_audio:
                logger.error("No audio data to assess")
                return None

            logger.info(f"Combined audio size: {len(combined_audio)} bytes")

            # Check minimum audio length (at least 1 second of 24kHz 16-bit mono audio = 48000 bytes)
            if len(combined_audio) < 48000:
                logger.warning(f"Audio might be too short: {len(combined_audio)} bytes")

            # Create WAV format audio
            wav_audio = self._create_wav_audio(combined_audio)

            # Perform assessment
            return await self._perform_assessment(wav_audio, reference_text)

        except Exception as e:
            logger.error(f"Error in pronunciation assessment: {e}")
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
                    logger.error(f"Error decoding audio chunk: {e}")

        return combined_audio

    def _create_wav_audio(self, audio_bytes: bytearray) -> bytes:
        """Create WAV format audio from raw PCM bytes."""
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(24000)  # 24kHz
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        return wav_buffer.read()

    async def _perform_assessment(
        self, wav_audio: bytes, reference_text: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Perform the actual pronunciation assessment."""
        logger.info(
            f"Starting pronunciation assessment with audio size: {len(wav_audio)} bytes"
        )
        logger.info(f"Reference text: {reference_text or 'None'}")
        logger.info(f"Speech key configured: {'Yes' if self.speech_key else 'No'}")
        logger.info(f"Speech region: {self.speech_region}")

        # Create speech configuration
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key, region=self.speech_region
        )
        speech_config.speech_recognition_language = "en-US"

        # Configure pronunciation assessment
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text or "",
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation_config.enable_prosody_assessment()

        # Create audio stream
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=24000,
            bits_per_sample=16,
            channels=1,
            wave_stream_format=speechsdk.audio.AudioStreamWaveFormat.PCM,
        )

        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
        push_stream.write(wav_audio)
        push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Create recognizer and apply configuration
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config, language="en-US"
        )
        pronunciation_config.apply_to(speech_recognizer)

        # Perform recognition
        result = await asyncio.get_event_loop().run_in_executor(
            None, speech_recognizer.recognize_once
        )

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
            return {
                "accuracy_score": pronunciation_result.accuracy_score,
                "fluency_score": pronunciation_result.fluency_score,
                "completeness_score": pronunciation_result.completeness_score,
                "prosody_score": getattr(pronunciation_result, "prosody_score", None),
                "pronunciation_score": pronunciation_result.pronunciation_score,
                "words": self._extract_word_details(result),
            }
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speechsdk.CancellationDetails(result)
            logger.error(f"Speech recognition canceled: {cancellation_details.reason}")
            
            if hasattr(cancellation_details, 'error_code'):
                logger.error(f"Error code: {cancellation_details.error_code}")
            
            if hasattr(cancellation_details, 'error_details'):
                logger.error(f"Error details: {cancellation_details.error_details}")
            
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                logger.error("Authentication or configuration error likely")
            return None
        else:
            logger.error(f"Speech recognition failed: {result.reason}")
            return None

    def _extract_word_details(self, result) -> List[Dict[str, Any]]:
        """Extract word-level pronunciation details."""
        try:
            json_result = json.loads(
                result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult, "{}"
                )
            )

            words = []
            if "NBest" in json_result and json_result["NBest"]:
                for word_info in json_result["NBest"][0].get("Words", []):
                    words.append(
                        {
                            "word": word_info.get("Word", ""),
                            "accuracy": word_info.get(
                                "PronunciationAssessment", {}
                            ).get("AccuracyScore", 0),
                            "error_type": word_info.get(
                                "PronunciationAssessment", {}
                            ).get("ErrorType", "None"),
                        }
                    )

            return words
        except Exception as e:
            logger.error(f"Error extracting word details: {e}")
            return []
