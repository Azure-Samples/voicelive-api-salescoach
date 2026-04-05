"""Integration tests for Azure Speech SDK - pronunciation assessment against real service.

These tests use Azure Speech SDK to synthesize test audio via TTS, then assess pronunciation.
This solves the "no microphone in CI" problem by using TTS to generate the audio input.

Run with: pytest tests/integration/test_speech_integration.py -v
"""

import asyncio
import os

from tests.conftest import requires_speech


def _get_speech_config_with_auth(region: str):
    """Create a SpeechConfig using either key or DefaultAzureCredential token."""
    import azure.cognitiveservices.speech as speechsdk

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    if speech_key:
        return speechsdk.SpeechConfig(subscription=speech_key, region=region)

    # Use DefaultAzureCredential to get a FRESH token for the Speech resource
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")

    # Get the Speech resource host endpoint for the custom domain
    resource_name = os.getenv("AI_FOUNDRY_RESOURCE_NAME", "")
    speech_resource_name = resource_name.replace("aifoundry-", "speech-") if resource_name else ""

    if speech_resource_name:
        # Use the custom domain endpoint
        # Must set auth_token separately from endpoint per SDK requirement
        endpoint = f"https://{speech_resource_name}.cognitiveservices.azure.com"
        speech_config = speechsdk.SpeechConfig(endpoint=endpoint)
        speech_config.authorization_token = token.token
    else:
        speech_config = speechsdk.SpeechConfig(auth_token=token.token, region=region)

    return speech_config


def _synthesize_audio(text: str, region: str) -> bytes:
    """Use Azure TTS to synthesize audio, return raw PCM bytes.

    This gives us realistic audio to feed back into pronunciation assessment
    without needing a microphone.
    """
    import azure.cognitiveservices.speech as speechsdk

    speech_config = _get_speech_config_with_auth(region)
    speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm)
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    elif result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        raise RuntimeError(f"Speech synthesis canceled: {details.reason}, {details.error_details}")
    else:
        raise RuntimeError(f"Speech synthesis failed: {result.reason}")


def _get_region(azure_env):
    """Get Speech region."""
    return azure_env.get("speech_region") or os.getenv("AZURE_SPEECH_REGION", "eastus2")


@requires_speech
class TestSpeechSDKIntegration:
    """Integration tests against real Azure Speech Services."""

    def test_speech_sdk_import(self):
        """Verify Speech SDK can be imported and version is available."""
        import azure.cognitiveservices.speech as speechsdk

        assert hasattr(speechsdk, "__version__")
        version = speechsdk.__version__
        parts = version.split(".")
        assert int(parts[0]) >= 1
        assert int(parts[1]) >= 47  # Minimum we support

    def test_tts_synthesis(self, azure_env):
        """Test text-to-speech synthesis produces audio."""
        region = _get_region(azure_env)
        audio_data = _synthesize_audio("Hello world", region)
        assert len(audio_data) > 1000  # Should have meaningful audio data

    def test_pronunciation_assessment_with_synthesized_audio(self, azure_env):
        """Test full pronunciation assessment using TTS-generated audio.

        Flow: text -> TTS -> PCM audio -> pronunciation assessment -> scores
        """
        import azure.cognitiveservices.speech as speechsdk

        region = _get_region(azure_env)
        reference_text = "Hello, I would like to discuss our enterprise solution with you today."

        # Step 1: Synthesize audio from reference text
        pcm_audio = _synthesize_audio(reference_text, region)
        assert len(pcm_audio) > 0

        # Step 2: Set up pronunciation assessment
        speech_config = _get_speech_config_with_auth(region)
        speech_config.speech_recognition_language = "en-US"

        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True,
        )
        pronunciation_config.enable_prosody_assessment()

        # Step 3: Create audio config from PCM data
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=24000,
            bits_per_sample=16,
            channels=1,
            wave_stream_format=speechsdk.audio.AudioStreamWaveFormat.PCM,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
        push_stream.write(pcm_audio)
        push_stream.close()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Step 4: Run recognition
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
            language="en-US",
        )
        pronunciation_config.apply_to(recognizer)

        result = recognizer.recognize_once()

        # Step 5: Verify results
        assert (
            result.reason == speechsdk.ResultReason.RecognizedSpeech
        ), f"Expected RecognizedSpeech, got {result.reason}"

        pron_result = speechsdk.PronunciationAssessmentResult(result)

        # TTS-generated audio should score very high on pronunciation
        assert pron_result.accuracy_score >= 70, f"Accuracy score {pron_result.accuracy_score} too low for TTS audio"
        assert pron_result.fluency_score >= 60, f"Fluency score {pron_result.fluency_score} too low"
        assert pron_result.pronunciation_score >= 60, f"Pronunciation score {pron_result.pronunciation_score} too low"

    def test_pronunciation_assessor_class_integration(self, azure_env):
        """Test the PronunciationAssessor class audio preparation and result building.

        Tests the app class methods that handle audio data, without running a
        separate recognition (covered by test_pronunciation_assessment_with_synthesized_audio).
        """
        import base64

        region = _get_region(azure_env)

        # Synthesize test audio
        reference_text = "Thank you for meeting with me today."
        pcm_audio = _synthesize_audio(reference_text, region)

        # Test the audio preparation path from the actual PronunciationAssessor class
        from src.services.analyzers import PronunciationAssessor

        assessor = PronunciationAssessor()

        # Test _prepare_audio_data correctly decodes, combines, and returns audio
        encoded = base64.b64encode(pcm_audio).decode("utf-8")
        audio_chunks = [
            {"type": "user", "data": encoded},
            {"type": "assistant", "data": "ignore_this"},  # filtered out
        ]

        loop = asyncio.new_event_loop()
        try:
            combined = loop.run_until_complete(assessor._prepare_audio_data(audio_chunks))
        finally:
            loop.close()

        assert len(combined) == len(pcm_audio)
        assert bytes(combined) == pcm_audio

        # Test _create_wav_audio produces valid WAV with correct header
        wav_data = assessor._create_wav_audio(bytearray(pcm_audio))
        assert len(wav_data) > len(pcm_audio)
        # WAV starts with "RIFF"
        assert wav_data[:4] == b"RIFF"

        # Test _create_audio_config doesn't raise
        audio_cfg = assessor._create_audio_config(pcm_audio)
        assert audio_cfg is not None

        # Test _create_pronunciation_config returns valid config
        pron_cfg = assessor._create_pronunciation_config(reference_text)
        assert pron_cfg is not None
