"""
This module provides a class for real-time speech-to-text transcription using the Google Cloud Speech-to-Text API. Mostly copied from https://cloud.google.com/speech-to-text/docs/transcribe-streaming-audio?hl=zh-cn#perform_streaming_speech_recognition_on_an_audio_stream.
"""

import queue
import re
import sys
import time
import pyaudio
from google.cloud import speech
from typing import Callable, Optional, Iterator, List, Any, Tuple, Dict


# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
SILENCE_THRESHOLD = 9999999  # Set to a very high value to effectively disable automatic stopping


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate: int = RATE, chunk: int = CHUNK) -> None:
        """Initialize the microphone stream.
        
        Args:
            rate: Audio sampling rate.
            chunk: Audio chunk size.
        """
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True
        self._audio_interface = None
        self._audio_stream = None

    def __enter__(self) -> 'MicrophoneStream':
        """Set up the audio stream.
        
        Returns:
            The MicrophoneStream instance.
        """
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self) -> None:
        """Close the stream when exiting the context."""

        if self._audio_stream:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        if self._audio_interface:
            self._audio_interface.terminate()

    def _fill_buffer(
        self,
        in_data: bytes,
    ) -> Tuple[None, int]:
        """Continuously collect data from the audio stream, into the buffer.

        Args:
            in_data: The audio data as a bytes object

        Returns:
            A tuple containing None and a flag to continue audio processing.
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self) -> Iterator[bytes]:
        """Generate audio chunks from the stream of audio data.

        Returns:
            A generator that outputs audio chunks.
        """
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


class SpeechTranscriber:
    """Class for handling real-time speech-to-text conversion.
    
    This class encapsulates the functionality of the Google Speech-to-Text API,
    providing methods for starting/stopping transcription, processing transcription
    results, and handling callbacks.
    """
    
    def __init__(
        self, 
        api_key: str, 
        language_code: str = 'en-US',
        rate: int = RATE, 
        chunk: int = CHUNK,
        silence_threshold: int = SILENCE_THRESHOLD
    ) -> None:
        """Initialize the transcriber.
        
        Args:
            api_key: Google Cloud Speech API key.
            language_code: Language code, defaults to English.
            rate: Audio sampling rate.
            chunk: Audio chunk size.
            silence_threshold: Silence duration threshold in seconds to stop recognition.
                               Set to a very high value to effectively disable automatic stopping.
        """
        self.api_key = api_key
        self.language_code = language_code
        self.rate = rate
        self.chunk = chunk
        self.silence_threshold = silence_threshold
        
        # Initialize Google Speech client
        self.client = speech.SpeechClient(client_options={'api_key': api_key})
        
        # Create recognition config
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language_code,
            enable_automatic_punctuation=True,
            profanity_filter=True,
        )
        
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=self.config, interim_results=True
        )
        
        # Status flags
        self.is_listening = False
        self.stop_listening = False
        
        # Save final transcription text
        self.final_transcript = ''
        
        # Callback functions
        self.on_interim_result: Optional[Callable[[str], None]] = None
        self.on_final_result: Optional[Callable[[str], None]] = None
        
    def start_listening(
        self,
        on_interim_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        audio_generator: Optional[Iterator[bytes]] = None
    ) -> None:
        """Start listening and transcribing speech.
        
        Args:
            on_interim_result: Callback function to call when an interim result is available.
            on_final_result: Callback function to call when a final result is available.
            audio_generator: Optional audio generator; if None, use microphone.
        """
        self.on_interim_result = on_interim_result
        self.on_final_result = on_final_result
        self.is_listening = True
        self.stop_listening = False
        self.final_transcript = ''
        
        # If no audio generator is provided, use microphone
        if audio_generator is None:
            with MicrophoneStream(self.rate, self.chunk) as stream:
                self._process_audio_stream(stream.generator())
        else:
            self._process_audio_stream(audio_generator)
            
    def stop_listening(self) -> str:
        """Stop listening.
        
        Returns:
            The final transcription text.
        """
        self.stop_listening = True
        self.is_listening = False
        return self.final_transcript
        
    def _process_audio_stream(self, audio_generator: Iterator[bytes]) -> None:
        """Process the audio stream and transcribe.
        
        Args:
            audio_generator: Generator that produces audio chunks.
        """
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )
        
        try:
            responses = self.client.streaming_recognize(self.streaming_config, requests)
            self._process_responses(responses)
        except Exception as e:
            print(f'Error in transcription: {e}')
            
    def _process_responses(self, responses: Iterator[speech.StreamingRecognizeResponse]) -> None:
        """Process responses from the Speech API.
        
        Args:
            responses: Iterator of streaming recognition responses.
        """
        num_chars_printed = 0
        last_activity_time = time.time()
        current_sentence = ''
        final_transcript = ''
        
        for response in responses:
            if self.stop_listening:
                break
                
            if not response.results:
                continue
                
            # Check silence duration
            current_time = time.time()
            if self.silence_threshold > 0 and current_time - last_activity_time > self.silence_threshold:
                print('Detected silence exceeding threshold, stopping recognition...')
                break
                
            # For streaming recognition, we only care about the first result
            result = response.results[0]
            if not result.alternatives:
                continue
                
            # Get transcription text
            transcript = result.alternatives[0].transcript
            
            # Process interim results
            if not result.is_final:
                # For non-final results, only update the current sentence, don't accumulate to final text
                current_sentence = transcript
                
                if self.on_interim_result:
                    self.on_interim_result(transcript)
                    
                num_chars_printed = len(transcript)
                last_activity_time = time.time()
            else:
                # Process final results - add to final text
                if self.on_final_result:
                    self.on_final_result(transcript)
                
                # Add to final transcript, only adding finalized text
                final_transcript += ' ' + transcript.strip()
                
                # Update instance variable, so other methods can access it
                self.final_transcript = final_transcript.strip()
                self.final_transcript = re.sub(r'\s+', ' ', self.final_transcript)
                
                # Clear current sentence
                current_sentence = ''
                
                last_activity_time = time.time()
                
                # If exit keyword is detected, exit recognition
                if re.search(r'\b(exit|quit)\b', transcript, re.I):
                    print('Exit command detected..')
                    break
                    
                num_chars_printed = 0
                
        # Ensure final text is properly processed
        if final_transcript:
            self.final_transcript = final_transcript.strip()
            self.final_transcript = re.sub(r'\s+', ' ', self.final_transcript)
        elif current_sentence:
            # If no final result but current sentence exists, save it too
            self.final_transcript = current_sentence.strip()
                
        # Ensure final callback is called on exit
        if self.on_final_result and self.final_transcript and not self.stop_listening:
            self.on_final_result(self.final_transcript)

    @staticmethod
    def get_audio_frames_from_stream(
        stream: pyaudio.Stream, 
        frames_list: List[bytes], 
        is_recording_flag: Callable[[], bool]
    ) -> None:
        """Get frames from an audio stream and add them to a list.
        
        This is a helper method for adding audio frames to a list when recording audio.
        
        Args:
            stream: PyAudio stream object.
            frames_list: List to add frames to.
            is_recording_flag: Function that returns whether to continue recording.
        """
        while is_recording_flag():
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames_list.append(data)


def listen_print_loop(responses: Iterator[speech.StreamingRecognizeResponse]) -> str:
    """Iterate through server responses and print them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.

    Args:
        responses: Iterator of server responses

    Returns:
        The transcribed text.
    """
    num_chars_printed = 0
    last_activity_time = time.time()
    final_transcript = ''
    current_sentence = ''
    
    for response in responses:
        if not response.results:
            continue

        # Check if there has been 5 seconds without audio activity
        current_time = time.time()
        if current_time - last_activity_time > SILENCE_THRESHOLD:
            print('Found silence for 5 seconds, stopping recognition...')
            break
            
        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            # For non-final results, only update the current sentence, don't accumulate to final text
            current_sentence = transcript
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)
            # Update last activity time
            last_activity_time = time.time()
        else:
            # For final results, add current sentence to final_transcript
            print(transcript + overwrite_chars)
            # Add to final transcript, only adding finalized text
            final_transcript += ' ' + transcript.strip()
            # Clear current sentence
            current_sentence = ''
            # Update last activity time
            last_activity_time = time.time()
            
            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            num_chars_printed = 0
    
    # Remove leading and trailing spaces and ensure words are separated by only one space
    final_transcript = final_transcript.strip()
    final_transcript = re.sub(r'\s+', ' ', final_transcript)
    
    print('final transcript:', final_transcript)
    return final_transcript


def main(api_key: str) -> None:
    """Transcribe speech from audio file."""
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-US'  # a BCP-47 language tag
    client = speech.SpeechClient(client_options={'api_key': api_key})
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
        enable_automatic_punctuation=True,  # Enable automatic punctuation
        profanity_filter=True,   # Enable profanity filtering
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_loop(responses)



if __name__ == '__main__':
    main()