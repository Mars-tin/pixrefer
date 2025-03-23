"""Mask Description Evaluator.

This tool evaluates how well descriptions of object masks can be understood by others.
It loads previously collected mask descriptions and their associated image,
displays each description to users, and asks them to click on where they think the object is.
The tool records the guessed locations and calculates the accuracy based on whether
the click is inside the mask or the distance to the nearest mask point.
"""

import argparse
import json
import logging
import os
import tkinter as tk
import traceback
import numpy as np
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Tuple, Optional

from PIL import ImageDraw, Image

from pixrefer.core.utils import ensure_dir_exists, load_data
from pixrefer.interface.base_interface import BaseInterface

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ACC_MAX_DIST = 50


class MaskDescriptionEvaluator(BaseInterface):
    """A class for evaluating how well mask descriptions can be understood.

    This class loads previously saved mask descriptions, shows them to users,
    and asks users to click on where they think the described object is located.
    It then calculates and records the accuracy of these guesses based on whether
    the click is within the mask or the distance to the nearest mask point.
    """
    def __init__(self, 
                image_path: str, 
                json_path: str,
                mask_data: Dict[str, Any],
                mask_dir: str,
                output_dir: str = 'output',
                on_complete_callback: Optional[callable] = None,
                current_position: int = None,  # Current position in dataset
                total_images: int = None) -> None:  # Total number of images
        """Initialize the evaluator with mask data and an image.

        Args:
            image_path: Path to the image file.
            json_path: Path to the JSON file containing descriptions.
            mask_data: Dictionary containing mask path and description.
            mask_dir: Directory containing mask images.
            output_dir: Directory to save the evaluation results. Defaults to 'output'.
            on_complete_callback: Function to call when evaluation is complete. Optional.
            current_position: Current position in the dataset (1-based). Optional.
            total_images: Total number of images in the dataset. Optional.
        """
        
        # Build title including position information
        title = f'Mask Description Evaluator - {os.path.basename(image_path)}'

        # Store position information as instance attributes
        self.current_position = current_position
        self.total_images = total_images
        
        # Initialize the base interface
        super().__init__(
            image_path=image_path,
            title=title,
            initial_scale=0.5,
            on_complete_callback=on_complete_callback,
            current_position=current_position,
            total_images=total_images
        )
        
        # Flag to track if comparison is shown
        self.comparison_shown = False

        # Set up evaluation tracking
        self.json_path = json_path
        self.mask_data = mask_data
        self.mask_dir = mask_dir
        self.total_masks = 1  # Only one mask per item now
        self.guesses: List[Tuple[int, int]] = []
        self.distances: List[float] = []
        self.in_mask: List[int] = []  # Track if each guess was inside the mask, 0 for outside, 1 for inside

        # Set up output directory
        self.output_dir = output_dir
        ensure_dir_exists(output_dir)

        # Flag whether results have been saved
        self.results_saved = False

        # Add evaluation-specific UI elements
        self._add_evaluation_ui()

        # Bind click event to image label
        self.image_label.bind('<Button-1>', self.handle_click)
        
        # Store the current guess
        self.current_guess = None
        self.current_distance = None
        self.current_in_mask = 0
        
        # Add new flags to record "cannot tell" and "multiple match" status
        self.cannot_tell = 0
        self.multiple_match = 0
        
        # Start the evaluation
        self.update_display()

    def _add_evaluation_ui(self) -> None:
        """Add evaluation-specific UI elements."""
        # Add instruction label
        self.instruction_label = ttk.Label(
            self.control_frame,
            text='Read the description below and click on the image where you think the object in the red box (you cannot see the red box) is located. Or select one of the special options.',
            wraplength=0  # Set to 0 to auto-adjust text to control panel width
        )
        self.instruction_label.pack(anchor=tk.W if not self.is_portrait else tk.CENTER, pady=(5, 0), fill=tk.X)

        # Add description display area using base class method
        if self.is_portrait:
            text_height = 10
        else:
            text_height = 5 
        self._add_text_display(height=text_height, readonly=True)
        self.description_display = self.text_display  # Alias for backward compatibility
        
        # Add special buttons frame
        self.special_button_frame = ttk.Frame(self.control_frame)
        self.special_button_frame.pack(fill=tk.X, pady=5)
        
        # Add "cannot tell" and "multiple match" buttons
        self.cannot_tell_button = ttk.Button(
            self.special_button_frame,
            text='Cannot Tell Where The Object Is',
            command=self.handle_cannot_tell
        )
        
        self.multiple_match_button = ttk.Button(
            self.special_button_frame,
            text='Multiple Match',
            command=self.handle_multiple_match
        )
        
        # Arrange buttons based on interface orientation
        if self.is_portrait:
            self.cannot_tell_button.pack(anchor=tk.CENTER, pady=5, fill=tk.X)
            self.multiple_match_button.pack(anchor=tk.CENTER, pady=5, fill=tk.X)
        else:
            self.cannot_tell_button.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
            self.multiple_match_button.pack(side=tk.RIGHT, padx=(5, 0), fill=tk.X, expand=True)
        
        # Add zoom controls using base class method
        self._add_zoom_controls()

        # Create a button frame to hold Undo and Confirm buttons (initially hidden)
        self.button_frame = ttk.Frame(self.control_frame)
        self.button_frame.pack(fill=tk.X, pady=5)
        
        # Create buttons but don't show them initially
        self.undo_button = ttk.Button(
            self.button_frame,
            text='Undo Last Guess',
            command=self.undo_last_guess
        )
        
        self.confirm_button = ttk.Button(
            self.button_frame,
            text='Confirm Guess',
            command=self.confirm_guess
        )
        
        # Initially hide the button frame
        self.button_frame.pack_forget()

        # Update status bar text
        self.update_status('Click on the image where you think the described object is located, or select one of the special options.')

    def handle_enter_key(self, event: Optional[tk.Event] = None) -> None:
        """Handle the Enter key press based on the current state.

        If user has made a guess but not confirmed, confirm the guess.
        If the comparison is shown, move to the next description.
        If all descriptions are completed, proceed to the next image.

        Args:
            event: The key event. Optional.
        """
        if self.comparison_shown:
            # If comparison is shown, proceed to next image
            self._finish_and_proceed()
        elif self.current_guess is not None:
            # If we have a guess but haven't confirmed, confirm it
            self.confirm_guess()

    def update_display(self) -> None:
        """Update the image display and description text."""
        # Update the image display using the base class method
        self.update_image_display()

        # Update the progress label using base class method
        self.update_progress(self.current_position, self.total_images)

        # Update the description text using base class method
        current_description = self.mask_data['description']
        self.update_text_display(current_description)

        # Reset current guess and comparison flag
        self.current_guess = None
        self.current_distance = None
        self.current_in_mask = 0
        
        # Reset special flags
        self.cannot_tell = 0
        self.multiple_match = 0
        
        self.comparison_shown = False

        # Load the current mask for evaluation
        mask_path = os.path.join(self.mask_dir, self.mask_data['mask_path'])
        self.current_mask = self._load_mask(mask_path)

        # Hide button frame
        self.button_frame.pack_forget()

    def _load_mask(self, mask_path: str) -> np.ndarray:
        """Load a mask image and convert it to a binary numpy array.
        
        Args:
            mask_path: Path to the mask image file.
            
        Returns:
            A binary numpy array where True indicates mask pixels.
        """
        if not os.path.exists(mask_path):
            logger.warning(f'Mask file not found: {mask_path}')
            # Return an empty mask with the same dimensions as the image
            return np.zeros((self.height, self.width), dtype=bool)
            
        try:
            mask_img = Image.open(mask_path).convert('L')
            
            # Resize if needed to match the original image dimensions
            if mask_img.size != (self.width, self.height):
                mask_img = mask_img.resize((self.width, self.height), Image.Resampling.NEAREST)
                
            # Convert to numpy array and binarize
            mask_array = np.array(mask_img)
            # Threshold at 128 to convert grayscale to binary
            binary_mask = mask_array > 128
            
            return binary_mask
        except Exception as e:
            logger.error(f'Error loading mask {mask_path}: {e}')
            return np.zeros((self.height, self.width), dtype=bool)

    def handle_click(self, event: tk.Event) -> None:
        """Handle mouse click on the image to record the guessed object location.

        Args:
            event: The Tkinter event containing click coordinates.
        """
        # Convert the scaled coordinates back to original image coordinates
        if self.display_scale_factor > 0:  # Avoid division by zero
            original_x = int(event.x / self.display_scale_factor)
            original_y = int(event.y / self.display_scale_factor)
        else:
            original_x, original_y = event.x, event.y

        # Make sure coordinates are within image bounds
        original_x = max(0, min(original_x, self.width - 1))
        original_y = max(0, min(original_y, self.height - 1))

        # If there's already a current guess, automatically undo it
        if self.current_guess is not None:
            # Reset the display to original image
            self.update_display()

        # Store the current guess
        self.current_guess = (original_x, original_y)

        # Check if the guess is within the mask - convert boolean to int (0 or 1)
        self.current_in_mask = 1 if self.current_mask[original_y, original_x] else 0

        # Calculate distance to the nearest mask point if not in mask
        if self.current_in_mask == 0:
            self.current_distance = self._calculate_distance_to_mask(original_x, original_y)
        else:
            self.current_distance = 0.0  # Inside mask, so distance is 0

        # Show only the user's guess first
        self.show_guess(self.current_guess)

        # Show guess buttons
        self._show_guess_buttons()

    def _calculate_distance_to_mask(self, x: int, y: int) -> float:
        """Calculate the minimum distance from a point to the mask.
        
        Uses a brute-force approach to find the nearest mask pixel.
        
        Args:
            x: X-coordinate of the point.
            y: Y-coordinate of the point.
            
        Returns:
            The minimum Euclidean distance to any mask pixel.
        """
        # Get mask pixel coordinates
        mask_indices = np.where(self.current_mask)
        if len(mask_indices[0]) == 0:  # Empty mask
            return float('inf')
            
        # Calculate distances to all mask pixels
        y_coords = mask_indices[0]
        x_coords = mask_indices[1]
        
        # Vectorized distance calculation
        distances = np.sqrt((x_coords - x)**2 + (y_coords - y)**2)
        
        # Return the minimum distance
        return float(np.min(distances))

    def _show_guess_buttons(self) -> None:
        """Show buttons related to the guess."""
        # Clear all widgets in the button frame
        for widget in self.button_frame.winfo_children():
            widget.destroy()
            
        # Create layout based on interface orientation
        if self.is_portrait:
            # For portrait mode, buttons are arranged vertically
            self.undo_button = ttk.Button(
                self.button_frame,
                text='Undo Last Guess',
                command=self.undo_last_guess
            )
            self.undo_button.pack(anchor=tk.CENTER, pady=5)
            
            self.confirm_button = ttk.Button(
                self.button_frame,
                text='Confirm Guess',
                command=self.confirm_guess
            )
            self.confirm_button.pack(anchor=tk.CENTER, pady=5)
        else:
            # For landscape mode, buttons are arranged horizontally
            self.undo_button = ttk.Button(
                self.button_frame,
                text='Undo Last Guess',
                command=self.undo_last_guess
            )
            self.undo_button.pack(side=tk.LEFT, padx=(0, 5))
            
            self.confirm_button = ttk.Button(
                self.button_frame,
                text='Confirm Guess',
                command=self.confirm_guess
            )
            self.confirm_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Show the button frame
        self.button_frame.pack(fill=tk.X, pady=5)

    def show_guess(self, guess_loc: Tuple[int, int]) -> None:
        """Show just the user's guess on the image.

        Args:
            guess_loc: The guessed coordinates (x, y).
        """
        # Create a copy of the original image
        image_copy = self.original_image.copy()
        draw = ImageDraw.Draw(image_copy)

        # Draw the guessed location as a blue dot
        marker_radius = max(5, int(self.display_scale_factor * 3))
        draw.ellipse(
            [(guess_loc[0] - marker_radius, guess_loc[1] - marker_radius),
             (guess_loc[0] + marker_radius, guess_loc[1] + marker_radius)],
            fill='blue',
            outline='white'
        )

        # Update the display with the drawn image
        self.update_image_display(image_copy)
        
        # Update status bar
        self.update_status("Click again to change your guess, or press Enter or click 'Confirm Guess' to see the correct answer.")

    def handle_cannot_tell(self) -> None:
        """Handle click on 'Cannot Tell Where The Object Is' button."""
        # Reset any existing guesses
        if self.current_guess is not None:
            self.update_display()
            
        # Set flags
        self.cannot_tell = 1
        self.multiple_match = 0
        self.current_guess = []  # Empty list indicates no specific location
        self.current_distance = 0
        self.current_in_mask = 0
        
        # Update status bar
        self.update_status("You selected 'Cannot Tell Where The Object Is'. Press Enter or click 'Confirm Guess' to proceed.")
        
        # Show buttons
        self._show_guess_buttons()
    
    def handle_multiple_match(self) -> None:
        """Handle click on 'Multiple Match' button."""
        # Reset any existing guesses
        if self.current_guess is not None:
            self.update_display()
            
        # Set flags
        self.multiple_match = 1
        self.cannot_tell = 0
        self.current_guess = []  # Empty list indicates no specific location
        self.current_distance = 0
        self.current_in_mask = 0
        
        # Update status bar
        self.update_status("You selected 'Multiple Match'. Press Enter or click 'Confirm Guess' to proceed.")
        
        # Show buttons
        self._show_guess_buttons()

    def confirm_guess(self) -> None:
        """Confirm the user's guess and display the mask."""
        if self.current_guess is None:
            return

        # Store the guess, distance, and mask status
        self.guesses.append(self.current_guess)
        self.distances.append(self.current_distance)
        self.in_mask.append(self.current_in_mask)

        # Unbind click event to prevent further guesses
        self.image_label.unbind('<Button-1>')

        # Hide the button frame
        self.button_frame.pack_forget()

        # Show the comparison
        self.show_comparison(self.current_guess, self.current_distance, self.current_in_mask)

    def show_comparison(self, guess_loc: Tuple[int, int], distance: float, in_mask: int) -> None:
        """Show a comparison between the mask and the guessed location.

        Args:
            guess_loc: The guessed coordinates (x, y).
            distance: The distance to the mask (0 if inside).
            in_mask: Whether the guess is inside the mask (1) or not (0).
        """
        # Create a copy of the original image
        image_copy = self.original_image.copy()
        
        # Overlay the mask with semi-transparency
        mask_overlay = Image.new('RGBA', image_copy.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(mask_overlay)
        
        # Draw the mask with green color
        mask_indices = np.where(self.current_mask)
        for y, x in zip(mask_indices[0], mask_indices[1]):
            draw_overlay.point((x, y), fill=(0, 255, 0, 128))  # Semi-transparent green
            
        # Convert image to RGBA if it isn't already
        if image_copy.mode != 'RGBA':
            image_copy = image_copy.convert('RGBA')
            
        # Composite the images
        image_copy = Image.alpha_composite(image_copy, mask_overlay)
        
        # Check if this is a special case
        if self.cannot_tell or self.multiple_match:
            # Directly show the mask overlay image without adding guess points or lines
            pass
        else:
            # Handle regular guess point case
            draw = ImageDraw.Draw(image_copy)
            
            # Draw the guessed location as a blue dot
            marker_radius = max(5, int(self.display_scale_factor * 3))
            marker_color = 'blue'
            
            draw.ellipse(
                [(guess_loc[0] - marker_radius, guess_loc[1] - marker_radius),
                 (guess_loc[0] + marker_radius, guess_loc[1] + marker_radius)],
                fill=marker_color,
                outline='white'
            )
            
            # If not in mask, draw a line to the nearest mask point
            if in_mask == 0 and distance < float('inf'):
                # Find the nearest mask point
                mask_indices = np.where(self.current_mask)
                y_coords = mask_indices[0]
                x_coords = mask_indices[1]
                
                distances = np.sqrt((x_coords - guess_loc[0])**2 + (y_coords - guess_loc[1])**2)
                nearest_idx = np.argmin(distances)
                
                nearest_point = (int(x_coords[nearest_idx]), int(y_coords[nearest_idx]))
                
                # Draw a line from the guess to the nearest mask point
                draw.line([guess_loc, nearest_point], fill='red', width=2)

        # Update image display
        self.update_image_display(image_copy)

        # Update status bar message
        if self.cannot_tell:
            status_text = "You selected 'Cannot Tell Where The Object Is'. Press Enter or click 'Next' to continue."
        elif self.multiple_match:
            status_text = "You selected 'Multiple Match'. Press Enter or click 'Next' to continue."
        elif in_mask == 1:
            status_text = "Your guess is inside the object! Press Enter or click 'Next' to continue."
        else:
            status_text = f"Your guess was {distance:.2f} pixels away from the object. Press Enter or click 'Next' to continue."
            
        self.update_status(status_text)

        # Set a flag to indicate we're in the comparison state
        self.comparison_shown = True

        # Remove any existing next button
        if hasattr(self, 'next_button'):
            self.next_button.destroy()

        # Add a 'Next' button to continue to next image
        self.next_button = ttk.Button(
            self.control_frame,
            text='Next',
            command=self._finish_and_proceed
        )
        self.next_button.pack(pady=10)

        # Save results after showing comparison
        self._save_results()
            
    def _finish_and_proceed(self) -> None:
        """Finish the current evaluation and proceed to the next image."""
        # Destroy the main window
        self.root.destroy()
        
        # Call the callback function if provided
        if self.on_complete_callback:
            self.on_complete_callback()

    def undo_last_guess(self) -> None:
        """Allow the user to undo their last guess and try again."""
        # Reset current guess
        self.current_guess = None
        self.current_distance = None
        self.current_in_mask = 0
        
        # Reset special flags
        self.cannot_tell = 0
        self.multiple_match = 0

        # Update the display to the original image
        self.update_display()

        # Rebind the click event
        self.image_label.bind('<Button-1>', self.handle_click)

        # Update status bar
        self.update_status('Previous guess removed. Click on the image again.')

        # Hide the button frame
        self.button_frame.pack_forget()

    def _save_results(self) -> None:
        """Save the evaluation results to a JSON file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Use image name (without extension) as part of the filename
        mask_name = os.path.splitext(os.path.basename(self.mask_data['mask_path']))[0]
        filename = f'{self.output_dir}/mask_{mask_name}.json'
        
        eval_item = {
            'guessed_position': [int(coord) for coord in self.guesses[0]] if isinstance(self.guesses[0], tuple) else self.guesses[0],
            'distance': float(self.distances[0]),
            'in_mask': int(self.in_mask[0]),  # Already an int (0 or 1)
            'cannot_tell': int(self.cannot_tell),  # New field
            'multiple_match': int(self.multiple_match)  # New field
        }
        
        # Create results dictionary
        result = {
            'sample_data': self.mask_data,
            'evaluation_data': eval_item
        }
        
        # Save results
        ensure_dir_exists(os.path.dirname(filename))
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        logger.info(f'Evaluation results saved to {filename}')
        self.results_filename = filename
        self.results_saved = True

    def on_closing(self) -> None:
        """Handle window closing event."""
        # If results have been saved, close directly
        if self.results_saved:
            self.root.destroy()
            if self.on_complete_callback:
                self.on_complete_callback()
            return
            
        # If annotation has started but not completed, warn user about data loss
        if self.current_guess is not None and not self.comparison_shown:
            if not messagebox.askyesno('Data Loss Warning', 
                                     f"You have not completed the evaluation of this image. All annotations for this image will be lost.\n\nAre you sure you want to close the window?"):
                # User chose not to close window, continue annotation
                return
        
        # User confirmed close or no annotations have been made
        if messagebox.askyesno('Confirm Close', 'Are you sure you want to close? No more images will be shown after closing.'):
            # Destroy window
            self.root.destroy()
            
            # Call the callback function if provided
            if self.on_complete_callback:
                self.on_complete_callback(cancelled=True)  # Pass cancelled flag to callback function


class BatchEvaluator:
    """A class for batch evaluation of mask descriptions from multiple JSON files."""
    
    def __init__(self, 
                 json_path: str, 
                 image_dir: str,
                 mask_dir: str,
                 output_dir: str,
                 max_samples: Optional[int] = None) -> None:
        """Initialize the batch evaluator.
        
        Args:
            json_path: Path to the JSON file with mask descriptions.
            image_dir: Directory containing the images.
            mask_dir: Directory containing the mask images.
            output_dir: Directory to save the evaluation results.
            max_samples: Maximum number of samples to process. If None, processes all.
        """
        self.json_path = json_path
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        self.output_dir = output_dir
        self.max_samples = max_samples
        
        # Load all data items from the JSON file
        self.data_items = load_data(json_path)
        logger.info(f'From {json_path} loaded {len(self.data_items)} items')
        
        if max_samples and max_samples < len(self.data_items):
            self.data_items = self.data_items[:max_samples]
            
        # Find the index to start from based on already completed images
        self.current_index = self._find_starting_index()
        self.total_samples = len(self.data_items)
        
        # Create output directory if it doesn't exist
        ensure_dir_exists(output_dir)

        # 添加标志，用于控制是否继续处理
        self.should_continue = True
        
    def _find_starting_index(self) -> int:
        """Find the index from which to start annotation.
        
        Checks the output directory for existing result files to determine
        where to resume annotation.
        
        Returns:
            The index to start annotation from.
        """
        # If output directory doesn't exist, start from beginning
        if not os.path.exists(self.output_dir):
            return 0
            
        # Get all result files in the output directory
        result_files = [f for f in os.listdir(self.output_dir) if f.endswith('.json')]
        
        # If no result files, start from beginning
        if not result_files:
            return 0
            
        # Extract the image name for each result file and track completed images
        completed_masks = set()
        for result_file in result_files:
            mask_name = result_file.replace('.json', '').replace('mask_', '')
            completed_masks.add(mask_name)
        logger.info(f'Completed masks: {completed_masks}')
        
        # Check each data item to see if its image has been evaluated
        for i, item in enumerate(self.data_items):
            mask_name = item.get('mask_path', '').replace('.png', '')
            # Check if this image is not in the completed list
            if mask_name and mask_name not in completed_masks:
                logger.info(f'Continue from index {i} (mask: {mask_name})')
                return i
                
        # If all images have been annotated, return the list length
        return len(self.data_items)
        
    def run(self) -> None:
        """Start the batch evaluation process."""
        if not self.data_items:
            logger.warning('No data items found in the specified JSON file.')
            return
            
        if self.current_index >= len(self.data_items):
            logger.info('All images have been annotated. Nothing to do.')
            return
            
        logger.info(f'Starting from image {self.current_index + 1} / {self.total_samples}')
        # self._process_next_item()
        self._process_all_items()
        
    def _process_all_items(self) -> None:
        """Process all data items in the list."""
        while self.current_index < len(self.data_items) and self.should_continue:
            try:
                # Get the current data item
                data_item = self.data_items[self.current_index]
                
                # Get image path from data or construct it      
                if 'image_path' in data_item and os.path.exists(data_item['image_path']):
                    image_path = data_item['image_path']
                else:
                    # Fallback to constructing path from image_id
                    image_id = data_item.get('image_id')
                    if not image_id:
                        logger.error(f'Processing item {self.current_index} has no image_id field')
                        # Terminate the entire process when an error occurs instead of moving to the next image
                        self.should_continue = False
                        return
                    image_path = os.path.join(self.image_dir, f'{image_id}.jpg')        
                
                logger.info(f'Processing file {self.current_index + 1}/{self.total_samples}: {data_item.get("image_id", "unknown")}')
                logger.info(f'Image path: {image_path}')

                # Create a temporary root window for non-initial items
                if self.current_index > 0:
                    temp_root = tk.Tk()
                    temp_root.destroy()
                    
                # Create a new MaskDescriptionEvaluator instance with position information
                app = MaskDescriptionEvaluator(
                    image_path=image_path,
                    json_path=self.json_path,
                    mask_data=data_item,
                    mask_dir=self.mask_dir,
                    output_dir=self.output_dir,
                    on_complete_callback=self._on_evaluation_complete,
                    current_position=self.current_index + 1,  # Current position (1-based)
                    total_images=self.total_samples  # Total number of images
                )
            
                # Run the application, this will block until the window is closed
                app.run()
                
                if not self.should_continue:
                    break
            
            except Exception as e:
                logger.error(f'Error processing item {self.current_index}: {e}')
                logger.error(traceback.format_exc())
                # Terminate the entire process when an error occurs instead of moving to the next image
                messagebox.showerror("Error", f"An error occurred while processing image {self.current_index + 1}:\n{str(e)}\n\nThe program will terminate.")
                self.should_continue = False
                return

    def _on_evaluation_complete(self, cancelled: bool = False) -> None:
        """Called when an evaluation is complete.
        
        Args:
            cancelled: Whether the evaluation was cancelled by the user.
        """
        # If user cancelled, don't process more items
        if cancelled:
            logger.info('User has cancelled the evaluation process.')
            self.should_continue = False
            return
            
        # Increment index
        self.current_index += 1
        
        # Set flag to continue processing next item
        self.should_continue = True
        
        # # Process the next item
        # if self.current_index < len(self.data_items):
        #     # Process the next item directly
        #     self._process_next_item()
        # else:
        #     logger.info(f'All {self.current_index} samples processed. Evaluation complete.')


def main() -> None:
    """Parse command-line arguments and run the mask description evaluator.

    Handles argument parsing and initializes the MaskDescriptionEvaluator with
    the provided parameters.
    """
    parser = argparse.ArgumentParser(description='Evaluate object mask descriptions.')
    parser.add_argument('--json_path', type=str, help='Path to the JSON file containing mask descriptions')
    parser.add_argument('--image_dir', type=str, help='Directory containing images')
    parser.add_argument('--mask_dir', type=str, help='Directory containing mask images')
    parser.add_argument('--output_dir', type=str, help='Directory to save evaluation results')
    parser.add_argument('--max_samples', type=int, default=None,
    help='Maximum number of samples to process in batch mode')

    args = parser.parse_args()

    # Check if required arguments are provided
    if args.json_path and args.image_dir and args.mask_dir:
        # Batch mode
        batch_evaluator = BatchEvaluator(
            json_path=args.json_path,
            image_dir=args.image_dir,
            mask_dir=args.mask_dir,
            output_dir=args.output_dir,
            max_samples=args.max_samples
        )
        batch_evaluator.run()
        return
    else:
        logger.error('Missing required parameters. Please provide --json_path, --image_dir, and --mask_dir.')
        parser.print_help()
        return


if __name__ == '__main__':
    main() 