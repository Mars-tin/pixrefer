"""Mask Region Description Collector.

This tool allows users to provide textual descriptions of object regions in images.
It displays images with bounding boxes around objects and prompts users to describe
the highlighted objects. The descriptions are collected and saved for later use.
"""

import argparse
import json
import logging
import os
import tkinter as tk
import threading
import wave
import traceback
import time
import pyaudio
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Dict, List, Optional
from PIL import Image, ImageTk


from pixrefer.core.utils import ensure_dir_exists, load_config, load_data
from pixrefer.interface.base_interface import BaseInterface
from pixrefer.interface.speech2text import SpeechTranscriber, RATE, CHUNK

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RECORD_SECONDS = 5
WAVE_OUTPUT_FORMAT = '{}_mask_{}.wav'

# Speech API key
API_KEY = load_config(config_name='api.google.key')

# Input modes
MODE_TEXT = 'text'
MODE_AUDIO = 'audio'

# Disable automatic silence detection - set to a very high value effectively disabling it
DISABLE_SILENCE_DETECTION = 999999


class MaskRegionDescriptionCollector(BaseInterface):
    """A class for collecting textual descriptions of object regions in images.

    This class creates a graphical interface that displays an image with bounding boxes
    around objects. It prompts the user to describe each highlighted object and
    collects these descriptions for later use.
    """

    def __init__(self,
                 current_sample: Dict[str, Any] = None, # Current sample
                 masks: List[str] = None,
                 output_json_dir: str = None,
                 output_audio_dir: str = None,
                 image_dir: str = None,
                 initial_scale: float = 0.5,
                 on_complete_callback: Optional[callable] = None,
                 current_position: int = None,  # Current position in dataset
                 total_images: int = None,  # Total number of images
                 ) -> None:
        """Initialize the mask region description collector.

        Args:
            current_sample: Current sample from the JSON file.
            masks: List of dictionaries containing mask/box information.
            output_json_dir: Directory to save the collected descriptions.
            output_audio_dir: Directory to save the audio recordings.
            image_dir: Directory containing the images.
            initial_scale: Initial scale factor for the display. Defaults to 0.5.
            on_complete_callback: Function to call when collection is complete. Optional.
            current_position: Current position in the dataset (1-based). Optional.
            total_images: Total number of images in the dataset. Optional.
        """

        # Store current sample
        self.current_sample = current_sample

        # Store image ID
        self.image_id = current_sample['image_id']

        # Store image path
        self.image_path = os.path.join(image_dir, f"boxed_{os.path.splitext(current_sample['mask_path'])[0]}.jpg")

        # Build title with position information if provided
        title = f'Mask Region Description Collector - {self.image_id}'
        if current_position is not None and total_images is not None:
            title += f' ({current_position} / {total_images})'

        # Initialize the base interface
        super().__init__(
            image_path=self.image_path,
            title=title,
            initial_scale=initial_scale
        )

        
        # Set up collection tracking
        self.masks = masks
        self.current_index = 0
        self.total_masks = len(self.masks)
        
        # Separate text descriptions and audio descriptions
        self.text_descriptions: List[str] = []
        self.audio_descriptions: List[str] = []
        self.audio_files: List[Optional[str]] = [None] * self.total_masks
        
        # Set up output directory
        self.output_json_dir = output_json_dir
        ensure_dir_exists(self.output_json_dir)
        
        # Set up audio output directory
        self.output_audio_dir = output_audio_dir
        ensure_dir_exists(self.output_audio_dir)
        
        # Store callback
        self.on_complete_callback = on_complete_callback

        # Flag to track if results have been saved
        self.results_saved = False
        
        # Input mode tracking
        self.current_input_mode = MODE_TEXT
        
        # Audio recording variables
        self.is_recording = False
        self.recording_thread = None
        self.audio_stream = None
        self.frames = []
        self.p = None
        self.transcription_started = False
        
        # Create speech transcriber
        self.transcriber = SpeechTranscriber(api_key=API_KEY)
        self.transcription_thread = None
        
        # Add collection-specific UI elements
        self._add_collection_ui()

        # Bind additional events
        self.root.bind('<Return>', self.handle_enter_key)
        
        # Set window close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start the collection with the first mask
        self.update_display()

        self.recording_message = "Recording... (Speak now). Please finish your recording in one time. To re-record, click the 'Stop Recording' button and the 'Start Recording' button again."

    def _add_collection_ui(self) -> None:
        """Add collection-specific UI elements."""
        # Add instruction label
        self.instruction_label = ttk.Label(
            self.control_frame,
            text='Please describe the highlighted object in the red box so it can be uniquely identified.',
            font=('Arial', 12),
            wraplength=400  # Set a default value, will be updated based on actual control panel width
        )
        self.instruction_label.pack(anchor=tk.W if not self.is_portrait else tk.CENTER, pady=(5, 0), fill=tk.X)
        
        # Set text wrapping after interface creation
        self.root.after(100, self.update_text_wrapping)
        
        # Bind widget size change event 
        self.control_frame.bind('<Configure>', lambda e: self.update_text_wrapping())
        
        # Add input mode and control frame
        self.input_control_frame = ttk.Frame(self.control_frame)
        self.input_control_frame.pack(fill=tk.X, pady=5)
        
        # Add Text/Audio toggle buttons
        self.text_button = ttk.Button(
            self.input_control_frame,
            text='Text',
            command=lambda: self.switch_input_mode(MODE_TEXT),
            style='Accent.TButton'
        )
        self.text_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.audio_button = ttk.Button(
            self.input_control_frame,
            text='Audio',
            command=lambda: self.switch_input_mode(MODE_AUDIO)
        )
        self.audio_button.pack(side=tk.LEFT)
        
        # Add audio controls (initially hidden)
        self.audio_controls_frame = ttk.Frame(self.input_control_frame)
        
        # Add record/stop button
        self.record_button = ttk.Button(
            self.audio_controls_frame,
            text='Start Recording',
            command=self.toggle_recording
        )
        self.record_button.pack(side=tk.LEFT, padx=5)
        
        # Add description state labels
        self.description_state_frame = ttk.Frame(self.control_frame)
        if not self.is_portrait:
            self.description_state_frame.pack(side=tk.RIGHT, in_=self.input_control_frame)
        else:
            self.description_state_frame.pack(fill=tk.X, pady=5)
        
        self.has_text_label = ttk.Label(
            self.description_state_frame, 
            text='Text ✓', 
            foreground='green'
        )
        
        self.has_audio_label = ttk.Label(
            self.description_state_frame, 
            text='Audio ✓', 
            foreground='green'
        )
        
        # Add unified input area
        self.description_frame = ttk.LabelFrame(self.control_frame, text='Description')
        self.description_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.description_input = scrolledtext.ScrolledText(
            self.description_frame,
            height=5,
            wrap=tk.WORD,
            font=('Arial', 12)
        )
        self.description_input.pack(fill=tk.X, pady=5, padx=5)
        
        # Add save button
        self.save_button = ttk.Button(
            self.description_frame,
            text='Save Description',
            command=self.save_current_description
        )
        self.save_button.pack(side=tk.RIGHT, pady=5, padx=5)
        
        self._add_zoom_controls()
        
        # Add submit button (navigation button)
        self.submit_button = ttk.Button(
            self.control_frame,
            text='Next Image (Enter)',
            command=self.handle_enter_key 
        )
        self.submit_button.pack(anchor=tk.E, pady=10)

        # Update status bar text
        self.status_bar.configure(
            text='Please describe the highlighted object in the red box.',
            wraplength=400  # Set a default value, will be updated based on actual control panel width
        )
        
        # Set focus to description input
        self.description_input.focus_set()

    def switch_input_mode(self, mode: str) -> None:
        """Switch between input modes (text or audio).
        
        Args:
            mode: The input mode to switch to (MODE_TEXT or MODE_AUDIO).
        """
        if self.current_input_mode == mode:
            return
            
        # Save current content to appropriate description
        if self.current_input_mode == MODE_TEXT:
            # Save current text description before switching
            text = self.description_input.get('1.0', 'end-1c').strip()
            if text:
                if self.current_index < len(self.text_descriptions):
                    self.text_descriptions[self.current_index] = text
                else:
                    while len(self.text_descriptions) <= self.current_index:
                        self.text_descriptions.append('')
                    self.text_descriptions[self.current_index] = text
                # Update status indicator
                self._update_description_state_indicators()
                
        elif self.current_input_mode == MODE_AUDIO:
            # Save current audio description before switching
            text = self.description_input.get('1.0', 'end-1c').strip()
            if text and text != self.recording_message:
                if self.current_index < len(self.audio_descriptions):
                    self.audio_descriptions[self.current_index] = text
                else:
                    while len(self.audio_descriptions) <= self.current_index:
                        self.audio_descriptions.append('')
                    self.audio_descriptions[self.current_index] = text
                # Update status indicator
                self._update_description_state_indicators()
                
        # Stop any ongoing recording
        if self.is_recording:
            self.stop_recording()
            
        # Update mode
        self.current_input_mode = mode
        
        # Update button styles
        if mode == MODE_TEXT:
            self.text_button.configure(style='Accent.TButton')
            self.audio_button.configure(style='')
            # Hide audio controls
            self.audio_controls_frame.pack_forget()
            # Update description frame label
            self.description_frame.configure(text='Text Description')
            
        else:  # MODE_AUDIO
            self.audio_button.configure(style='Accent.TButton')
            self.text_button.configure(style='')
            # Show audio controls
            self.audio_controls_frame.pack(side=tk.LEFT, padx=5, after=self.audio_button)
            # Update description frame label
            self.description_frame.configure(text='Audio Description')
        
        # Load appropriate content to description input
        self._load_description_content()

    def _load_description_content(self) -> None:
        """Load content into description input based on current mode."""
        # Clear description input
        self.description_input.configure(state=tk.NORMAL)
        self.description_input.delete('1.0', tk.END)
        
        if self.current_input_mode == MODE_TEXT:
            # Load text description if available
            if self.current_index < len(self.text_descriptions) and self.text_descriptions[self.current_index]:
                self.description_input.insert('1.0', self.text_descriptions[self.current_index])
            
        else:  # MODE_AUDIO
            # Load audio description if available
            if self.current_index < len(self.audio_descriptions) and self.audio_descriptions[self.current_index]:
                self.description_input.insert('1.0', self.audio_descriptions[self.current_index])
            else:
                # If we're in audio mode but no audio description, disable text editing
                self.description_input.configure(state=tk.DISABLED)
        
        # Update description state indicators
        self._update_description_state_indicators()

    def _update_description_state_indicators(self) -> None:
        """Update description state indicators, showing which description types have content."""
        # Check if there is a text description
        has_text = (self.current_index < len(self.text_descriptions) and 
                    self.text_descriptions[self.current_index])
        
        # Check if there is an audio description
        has_audio = (self.current_index < len(self.audio_descriptions) and 
                     self.audio_descriptions[self.current_index])
        
        # Update status indicator display based on whether there is description content
        if has_text:
            self.has_text_label.pack(side=tk.LEFT, padx=5)
        else:
            self.has_text_label.pack_forget()
            
        if has_audio:
            self.has_audio_label.pack(side=tk.LEFT, padx=5)
        else:
            self.has_audio_label.pack_forget()
        
        # 更新提交按钮状态
        self._update_submit_button_state()

    def toggle_recording(self) -> None:
        """Toggle audio recording on/off."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self) -> None:
        """Start recording audio from the microphone."""
        if self.is_recording:
            return
            
        # Clear previous audio file reference
        if self.current_index < len(self.audio_files):
            self.audio_files[self.current_index] = None
            
        # Clear description input and prepare for recording
        self.description_input.configure(state=tk.NORMAL)
        self.description_input.delete('1.0', tk.END)
        self.description_input.insert('1.0', self.recording_message)
        self.description_input.configure(state=tk.DISABLED)
        
        # Update button text
        self.record_button.configure(text='Stop Recording')
        
        # Reset recording variables
        self.frames = []
        self.is_recording = True
        self.transcription_started = False
        
        # Start recording in a separate thread
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        # Start transcription in a separate thread
        self.transcription_thread = threading.Thread(target=self.start_transcription)
        self.transcription_thread.daemon = True
        self.transcription_thread.start()
        
        # Update status bar to inform user that they need to manually stop recording
        self.status_bar.configure(
            text='Recording audio... Speak clearly into your microphone and click "Stop Recording" when done.'
        )

    def stop_recording(self) -> None:
        """Stop recording audio and save the file."""
        if not self.is_recording:
            return
            
        # Set flag to stop recording
        self.is_recording = False
        
        # Update button text
        if hasattr(self, 'record_button') and self.root.winfo_exists():
            self.record_button.configure(text='Start Recording')
        
        # If SpeechTranscriber is used, make sure to stop it as well
        if hasattr(self, 'transcriber') and self.transcriber:
            self.transcriber.stop_listening = True
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=1.0)
            
        # Wait for transcription thread to finish
        if self.transcription_thread and self.transcription_thread.is_alive():
            self.transcription_thread.join(timeout=1.0)
        
        # Get the final transcript from the transcriber
        final_transcript = ''
        if hasattr(self, 'transcriber') and self.transcriber:
            final_transcript = self.transcriber.final_transcript
        
        # Save the audio file
        if self.frames:
            audio_filename = WAVE_OUTPUT_FORMAT.format(self.image_id, self.current_index)
            audio_path = os.path.join(self.output_audio_dir, audio_filename)
            
            with wave.open(audio_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 2 bytes for 'int16'
                wf.setframerate(RATE)
                wf.writeframes(b''.join(self.frames))
            
            # Store the audio file path
            if self.current_index < len(self.audio_files):
                self.audio_files[self.current_index] = audio_path
            else:
                self.audio_files.append(audio_path)
                
            # Enable text editing and update with final transcript
            if hasattr(self, 'description_input') and self.root.winfo_exists():
                self.description_input.configure(state=tk.NORMAL)
                self.description_input.delete('1.0', tk.END)
                
                # Use the final transcript if available
                if final_transcript:
                    self.description_input.insert('1.0', final_transcript)
                    
                    # Save the final transcription to audio descriptions
                    if self.current_index < len(self.audio_descriptions):
                        self.audio_descriptions[self.current_index] = final_transcript
                    else:
                        while len(self.audio_descriptions) <= self.current_index:
                            self.audio_descriptions.append('')
                        self.audio_descriptions[self.current_index] = final_transcript
                    
                    # Save results immediately after recording stops
                    if self.output_json_dir and self.current_sample:
                        self._save_result()
                
                # Update status bar, clearly indicating text has been automatically saved
                if hasattr(self, 'status_bar') and self.root.winfo_exists():
                    self.status_bar.configure(
                        text=f'Audio recording saved to {audio_filename}. Transcription text has been automatically saved. You can edit the transcription and click "Save Description" to update the saved description.'
                    )
            else:
                logger.info(f'Audio recording saved to {audio_path}, but UI is no longer available.')
                
            # Update description state indicators if UI still exists
            if self.root.winfo_exists():
                self._update_description_state_indicators()
                
                # 更新提交按钮状态
                self._update_submit_button_state()
        else:
            if hasattr(self, 'status_bar') and self.root.winfo_exists():
                self.status_bar.configure(text='No audio was recorded. Please try recording again.')

    def record_audio(self) -> None:
        """Record audio from the microphone."""
        try:
            self.p = pyaudio.PyAudio()
            stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            self.audio_stream = stream
            
            while self.is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                self.frames.append(data)
                
            stream.stop_stream()
            stream.close()
            self.p.terminate()
            self.audio_stream = None
            self.p = None
            
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            self.status_bar.configure(text=f'Error recording audio: {str(e)}')
            self.is_recording = False
            self.record_button.configure(text='Start Recording')

    def start_transcription(self) -> None:
        """Start transcription using SpeechTranscriber."""
        try:
            # Define callback functions to update UI
            def on_interim_result(text):
                if not self.transcription_started:
                    # First time receiving results, clear "Recording..." text
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda: self.clear_and_update_transcription(text, False))
                    self.transcription_started = True
                else:
                    # Subsequent results, completely replace rather than accumulate
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda: self.clear_and_update_transcription(text, False))
                
            def on_final_result(text):
                # Update with final result
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, lambda: self.clear_and_update_transcription(text, True))
            
            # Create a generator to provide audio data from our frames list
            def audio_generator():
                i = 0
                while self.is_recording or i < len(self.frames):
                    if i < len(self.frames):
                        yield self.frames[i]
                        i += 1
                    else:
                        time.sleep(0.1)  # Avoid busy waiting
                
            # Start transcriber with silence detection disabled
            self.transcriber = SpeechTranscriber(
                api_key=API_KEY,
                silence_threshold=DISABLE_SILENCE_DETECTION  # Use very high value to disable automatic stopping
            )
            self.transcriber.start_listening(
                on_interim_result=on_interim_result,
                on_final_result=on_final_result,
                audio_generator=audio_generator()
            )
            
        except Exception as e:
            logger.error(f'Error in transcription: {e}')
            self.root.after(0, lambda: self.status_bar.configure(
                text=f'Error in speech transcription: {str(e)}'
            ))

    def clear_and_update_transcription(self, text: str, final: bool) -> None:
        """Clear text box and update transcription text.
        
        Args:
            text: Transcription text
            final: Whether this is the final transcription result
        """
        # Add a check to ensure the component still exists
        try:
            # Try using winfo_exists() to check if the component exists
            if not self.root.winfo_exists() or not hasattr(self, 'description_input'):
                return
                
            self.description_input.configure(state=tk.NORMAL)
            self.description_input.delete('1.0', tk.END)
            self.description_input.insert(tk.END, text)
            
            if not final and self.is_recording:
                self.description_input.configure(state=tk.DISABLED)
        except (tk.TclError, RuntimeError, AttributeError):
            # Catch any errors related to Tkinter components not existing
            pass

    def update_transcription(self, text: str, final: bool) -> None:
        """Update transcription text, accumulating with previous text rather than replacing.
        
        Args:
            text: New transcription text
            final: Whether this is the final transcription result
        """
        # For compatibility, retain this method but simply call clear_and_update_transcription
        self.clear_and_update_transcription(text, final)

    def save_current_description(self) -> None:
        """Save the current description."""
        description = self.description_input.get('1.0', 'end-1c').strip()

        if not description or description == self.recording_message:
            self.status_bar.configure(
                text='Please enter a description before saving.'
            )
            return

        # Save based on current input mode
        if self.current_input_mode == MODE_TEXT:
            if self.current_index < len(self.text_descriptions):
                self.text_descriptions[self.current_index] = description
            else:
                while len(self.text_descriptions) <= self.current_index:
                    self.text_descriptions.append('')
                self.text_descriptions[self.current_index] = description
            
            description_type = 'Text'
        else:  # MODE_AUDIO
            if self.current_index < len(self.audio_descriptions):
                self.audio_descriptions[self.current_index] = description
            else:
                while len(self.audio_descriptions) <= self.current_index:
                    self.audio_descriptions.append('')
                self.audio_descriptions[self.current_index] = description
            
            description_type = 'Audio'
        
        # Save results immediately after description is saved
        if self.output_json_dir and self.current_sample:
            self._save_result()
        
        # Update description state indicators
        self._update_description_state_indicators()
        
        # Update submit button state
        self._update_submit_button_state()
        
        # Update status
        self.status_bar.configure(
            text=f"{description_type} description saved: '{description[:50]}{'...' if len(description) > 50 else ''}'"
        )

    def handle_enter_key(self, event=None) -> None:
        """Handle the Enter key press to submit the current description."""
        # If all annotations are completed, pressing Enter should proceed to next step
        if self.current_index >= self.total_masks:
            self._finish_and_proceed()
        else:
            # Save current description (if any)
            description = self.description_input.get('1.0', 'end-1c').strip()
            if description and description != self.recording_message:
                # Save description based on current input mode
                self.save_current_description()
            
            # Check if both text and audio descriptions exist
            has_text = (self.current_index < len(self.text_descriptions) and 
                       self.text_descriptions[self.current_index])
            has_audio = (self.current_index < len(self.audio_descriptions) and 
                        self.audio_descriptions[self.current_index])
            
            # Must complete both text and audio descriptions to continue
            if not has_text:
                self.status_bar.configure(
                    text='You must provide a text description to continue. Please switch to "Text" mode and add a description.'
                )
                # Switch to text mode to allow user input
                if self.current_input_mode != MODE_TEXT:
                    self.switch_input_mode(MODE_TEXT)
                return
                
            if not has_audio:
                self.status_bar.configure(
                    text='You must provide an audio description to continue. Please switch to "Audio" mode and record a description.'
                )
                # Switch to audio mode to allow user recording
                if self.current_input_mode != MODE_AUDIO:
                    self.switch_input_mode(MODE_AUDIO)
                return
            
            # Both descriptions are completed, save results
            self._save_result()
            
            # Proceed to next image directly
            self._finish_and_proceed()

    def update_display(self) -> None:
        """Update the image display with the current mask highlighted."""
        if self.current_index >= self.total_masks:
            # We've gone through all masks, save and finish
            self._save_result()
            return

        # Get the current mask
        current_mask = self.masks[self.current_index]
        
        # Draw the bounding box on the image
        image_with_box = Image.open(self.image_path)
        
        # Resize the image
        scaled_image = image_with_box.resize(
            (int(self.width * self.display_scale_factor),
             int(self.height * self.display_scale_factor)),
            Image.Resampling.LANCZOS
        )
        
        # Convert to PhotoImage and update the label
        self.photo_image = ImageTk.PhotoImage(scaled_image)
        self.image_label.configure(image=self.photo_image)
        
        # Update scale label
        self.scale_label.configure(text=f'Scale: {self.display_scale_factor:.1f}x')
        
        # Reset to TYPE mode by default
        self.current_input_mode = MODE_TEXT
        self.text_button.configure(style='Accent.TButton')
        self.audio_button.configure(style='')
        self.audio_controls_frame.pack_forget()
        self.description_frame.configure(text='Text Description')
        
        # Load content for current mode
        self._load_description_content()
        
        # Update submit button state
        self._update_submit_button_state()
        
        # Set focus to input by default
        self.description_input.focus_set()

    def _save_result(self) -> None:
        """Save the collected descriptions to a JSON file.
        
        Creates a JSON file for the current sample with user descriptions and audio file information.
        """
        if not self.output_json_dir or not self.current_sample:
            logger.warning('Cannot save result: output_json_dir or current_sample not provided')
            return
        
        # Prepare to update current sample with descriptions
        if self.current_index >= 0 and self.current_index < len(self.text_descriptions):
            text_desc = self.text_descriptions[self.current_index]
            self.current_sample['user_text_des'] = text_desc
            
        if self.current_index >= 0 and self.current_index < len(self.audio_descriptions):
            audio_desc = self.audio_descriptions[self.current_index]
            self.current_sample['user_audio_des'] = audio_desc
            
        if self.current_index >= 0 and self.current_index < len(self.audio_files) and self.audio_files[self.current_index]:
            # Store only the basename of the audio file
            audio_basename = os.path.basename(self.audio_files[self.current_index])
            self.current_sample['user_audio_file'] = audio_basename
        
        # Create output file path using the mask ID
        mask_id = self.current_sample['mask_path'].replace('.png', '')
        output_path = os.path.join(self.output_json_dir, f'{mask_id}.json')
        
        # Write the updated sample to the JSON file
        try:
            with open(output_path, 'w') as f:
                json.dump(self.current_sample, f, indent=2)
            
            logger.info(f'Saved result for {mask_id} to {output_path}')
            self.results_saved = True
            
        except Exception as e:
            logger.error(f'Error saving result to {output_path}: {e}')

    def _finish_and_proceed(self) -> None:
        """Finish the current collection and proceed to the next image."""
        # Destroy the main window
        self.root.destroy()
        
        # Call the callback function if provided
        if self.on_complete_callback:
            self.on_complete_callback()

    def on_closing(self) -> None:
        """Handle window closing event."""
        # Guarantee the recording is stopped
        if hasattr(self, 'is_recording') and self.is_recording:
            self.is_recording = False
            
        # Guarantee the transcription is stopped
        if hasattr(self, 'transcriber') and self.transcriber:
            self.transcriber.stop_listening = True
            
        # If all descriptions are completed and saved results, just close
        if self.current_index >= self.total_masks and self.results_saved:
            self.root.destroy()
            if hasattr(self, 'on_complete_callback') and self.on_complete_callback:
                self.on_complete_callback()
            return
            
        # If we've started collecting but haven't completed all descriptions, warn about data loss
        if self.current_index > 0 and self.current_index < self.total_masks:
            if not messagebox.askyesno('Data Loss Warning', 
                                     f"You haven't completed all descriptions for this image. All annotations for this image will be discarded.\n\nDo you still want to close the window?"):
                # User chose not to close, continue collection
                return
        
        # User confirmed closing or hasn't made any annotations
        if messagebox.askyesno('Confirm Close', 'Are you sure you want to close? No more images will be shown after closing.'):
            # Destroy the window
            self.root.destroy()
            
            # Call the callback function if provided
            if hasattr(self, 'on_complete_callback') and self.on_complete_callback:
                self.on_complete_callback(cancelled=True)  # Pass cancelled flag to callback
        # Otherwise continue collection

    def _update_submit_button_state(self) -> None:
        """Update the submit button state based on the current index and descriptions."""
        # Check if both text and audio descriptions exist
        has_text = (self.current_index < len(self.text_descriptions) and 
                   self.text_descriptions[self.current_index])
        has_audio = (self.current_index < len(self.audio_descriptions) and 
                    self.audio_descriptions[self.current_index])
        
        # Only enable button when both descriptions exist
        if has_text and has_audio:
            self.submit_button.configure(state=tk.NORMAL)
            # Update button text to indicate that next image can be continued
            self.submit_button.configure(text='Next Image (Enter)')
            # Update status bar
            self.status_bar.configure(
                text='Both text and audio descriptions are completed, you can proceed to the next image.'
            )
        else:
            self.submit_button.configure(state=tk.DISABLED)
            # Update button text to indicate the tasks that need to be completed
            missing = []
            if not has_text:
                missing.append("Text")
            if not has_audio:
                missing.append("Audio")
            missing_str = " and ".join(missing)
            self.submit_button.configure(text=f'Please complete {missing_str} description before proceeding.')

    def update_text_wrapping(self) -> None:
        """Update text widget wrapping settings based on current control panel width."""
        # Get current control panel width
        control_width = self.control_frame.winfo_width()
        
        # If width is reasonable, update text wrapping settings
        if control_width > 50:  # Ensure widget has rendered and has reasonable width
            # Update instruction label
            self.instruction_label.configure(wraplength=control_width - 20)  # Leave some margin
            
            # Update status bar
            self.status_bar.configure(wraplength=control_width - 20)  # Leave some margin
            
            # For usability, adjust description label font size (optional)
            if self.is_portrait and control_width < 400:
                # If vertical and width is small, reduce font size
                self.instruction_label.configure(font=('Arial', 13))
                self.status_bar.configure(font=('Arial', 12))
            else:
                # Restore normal font size
                self.instruction_label.configure(font=('Arial', 13))
                self.status_bar.configure(font=('Arial', 11))


class BatchCollector:
    """A class for batch collection of mask region descriptions from multiple JSON files."""
    
    def __init__(self, 
                 json_path: str, 
                 image_dir: str,
                 output_json_dir: str,
                 output_audio_dir: str,
                 max_samples: Optional[int] = None) -> None:
        """Initialize the batch collector.
        
        Args:
            json_path: Path to JSON file with image and box information.
            image_dir: Directory containing the images.
            output_json_dir: Directory to save output JSON files.
            output_audio_dir: Directory to save audio recordings.
            max_samples: Maximum number of samples to process. If None, processes all.
        """
        self.json_path = json_path
        self.image_dir = image_dir
        self.output_json_dir = output_json_dir
        self.output_audio_dir = output_audio_dir
        self.max_samples = max_samples
        
        # Ensure output directories exist
        ensure_dir_exists(self.output_json_dir)
        ensure_dir_exists(self.output_audio_dir)
        
        # Load samples from JSON file
        self.samples = self._load_samples()
        logger.info(f'Loaded {len(self.samples)} samples from {json_path}')
        
        if max_samples and max_samples < len(self.samples):
            self.samples = self.samples[:max_samples]
            
        # Find the starting index (to resume from previously completed images)
        self.current_index = self._find_starting_index()
        self.total_samples = len(self.samples)
        
    def _load_samples(self) -> List[Dict[str, Any]]:
        """Load samples from the JSON file.
        
        Returns:
            List of samples from the JSON file.
        """
        try:
            samples = load_data(self.json_path)
            if self.max_samples and len(samples) > self.max_samples:
                samples = samples[:self.max_samples]
            return samples
        
        except Exception as e:
            logger.error(f'Error loading samples from {self.json_path}: {e}')
            return []
        
    def _find_starting_index(self) -> int:
        """Find the index to start collection from.
        
        Checks output directory for existing results to determine where to resume.
        
        Returns:
            Index to start collection from.
        """
        # Get completed mask IDs from output directory
        completed_masks = set()
        if os.path.exists(self.output_json_dir):
            for filename in os.listdir(self.output_json_dir):
                if filename.endswith('.json'):
                    # Extract mask ID (remove .json extension)
                    mask_id = os.path.splitext(filename)[0]
                    completed_masks.add(mask_id)
        
        # Check each sample to see if it has been processed
        for i, sample in enumerate(self.samples):
            if sample['mask_path'].replace('.png', '') not in completed_masks:
                logger.info(f'Resuming from index {i} (mask: {sample.get("mask_path", "unknown")})')
                return i
                
        # If all masks have been processed, return the length of the list
        return len(self.samples)
        
    def run(self) -> None:
        """Start the batch collection process."""
        if not self.samples:
            logger.warning('No samples found in the specified JSON file.')
            return
            
        if self.current_index >= len(self.samples):
            logger.info('All masks have already been annotated. Nothing to do.')
            return
            
        logger.info(f'Starting from mask {self.current_index + 1} of {self.total_samples}')
        self._process_next_item()
        
    def _process_next_item(self) -> None:
        """Process the next sample in the list."""
        if self.current_index >= len(self.samples):
            logger.info(f'All {self.current_index} masks processed. Collection complete!')
            return
            
        try:
            # Get the current sample
            sample = self.samples[self.current_index]
            mask_path = sample["mask_path"]
            masks = [mask_path]
            
            logger.info(f'Processing mask {self.current_index + 1}/{self.total_samples}: {mask_path}')
            
            # Destroy the temporary root window if it exists
            if self.current_index > 0:
                temp_root = tk.Tk()
                temp_root.destroy()
                
            # Create a new collector instance with position information in the title
            app = MaskRegionDescriptionCollector(
                current_sample=sample,  # Pass the current sample
                masks=masks,  # Pass mask data as a list
                output_json_dir=self.output_json_dir,
                output_audio_dir=self.output_audio_dir,
                image_dir=self.image_dir,
                on_complete_callback=self._on_collection_complete,
                current_position=self.current_index + 1,  # Current position
                total_images=self.total_samples,  # Total number of images
            )
            
            # Run the application, this will block until the window is closed
            app.run()
            
        except Exception as e:
            logger.error(f'Error processing item {self.current_index}: {e}')
            logger.error(traceback.format_exc())
            self.current_index += 1
            self._process_next_item()
            
    def _on_collection_complete(self, cancelled=False) -> None:
        """Called when a collection is complete.
        
        Args:
            cancelled: Whether the collection was cancelled by the user.
        """
        # If user cancelled, don't process more items
        if cancelled:
            logger.info("User has cancelled the collection process.")
            return
            
        # Increment index
        self.current_index += 1
        
        # Process the next item
        if self.current_index < len(self.samples):
            # Process the next item directly
            self._process_next_item()
        else:
            logger.info(f'All {self.current_index} samples processed. Collection complete!')


def main() -> None:
    """Parse command-line arguments and run the mask region description collector.

    Handles argument parsing and initializes the appropriate collector based on
    the provided parameters.
    """
    # Create argument parser
    parser = argparse.ArgumentParser(description='Collect descriptions of object regions in images.')
    
    # Add command line arguments
    parser.add_argument('--json_path', type=str, required=True,
                      help='Path to JSON file with image and box information')
    parser.add_argument('--boxed_image_dir', type=str, required=True,
                      help='Directory containing boxed images')
    parser.add_argument('--output_json_dir', type=str, required=True,
                      help='Directory to save output JSON files')
    parser.add_argument('--output_audio_dir', type=str, required=True,
                      help='Directory to save audio recordings')
    parser.add_argument('--max_samples', type=int, default=None,
                      help='Maximum number of samples to process (default: all)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if batch mode is enabled
    if args.json_path and args.boxed_image_dir:
        # Batch mode
        logger.info(f'Running in batch mode with parameters:')
        logger.info(f'  JSON path: {args.json_path}')
        logger.info(f'  Boxed images directory: {args.boxed_image_dir}')
        logger.info(f'  Output JSON directory: {args.output_json_dir}')
        logger.info(f'  Output audio directory: {args.output_audio_dir}')
        logger.info(f'  Max samples: {args.max_samples}')
        
        batch_collector = BatchCollector(
            json_path=args.json_path,
            image_dir=args.boxed_image_dir,
            output_json_dir=args.output_json_dir,
            output_audio_dir=args.output_audio_dir,
            max_samples=args.max_samples
        )
        batch_collector.run()
    
    else:
        logger.error('Error: You must provide --json_path and --boxed_image_dir for batch mode.')
        parser.print_help()


if __name__ == '__main__':
    main()