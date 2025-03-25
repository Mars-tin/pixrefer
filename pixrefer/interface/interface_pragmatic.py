"""Selection Evaluator.

This tool displays images to users and asks them to select from four fixed options:
- Left
- Small
- Light Gray
- Square

The tool records the user's selection and automatically proceeds to the next image.
It is based on the mask description evaluator but with simplified interaction.
"""

import argparse
import json
import logging
import os
import random
import tkinter as tk
import traceback
import numpy as np
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from pixrefer.core.utils import ensure_dir_exists, load_data
from pixrefer.interface.base_interface import BaseInterface

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SelectionEvaluator(BaseInterface):
    """A class for evaluating user selections from fixed options.

    This class loads images, presents them to users along with four fixed options,
    and records their selections. It automatically proceeds to the next image
    after a selection is made.
    """
    def __init__(self, 
                image_path: str, 
                json_path: str,
                image_data: Dict[str, Any],
                output_dir: str = 'output',
                on_complete_callback: Optional[callable] = None,
                current_position: int = None,  # Current position in dataset
                total_images: int = None) -> None:  # Total number of images
        """Initialize the evaluator with image data.

        Args:
            image_path: Path to the image file.
            json_path: Path to the JSON file containing image data.
            image_data: Dictionary containing image data.
            output_dir: Directory to save the evaluation results. Defaults to 'output'.
            on_complete_callback: Function to call when evaluation is complete. Optional.
            current_position: Current position in the dataset (1-based). Optional.
            total_images: Total number of images in the dataset. Optional.
        """
        
        # Build title including position information
        title = f'Pragmatics Preference - {os.path.basename(image_path)}'

        # Store position information as instance attributes
        self.current_position = current_position
        self.total_images = total_images
        
        # Initialize the base interface
        super().__init__(
            image_path=image_path,
            title=title,
            initial_scale=0.2,  # set to 0.2 for these big images
            on_complete_callback=on_complete_callback,
            current_position=current_position,
            total_images=total_images
        )

        # Set up evaluation tracking
        self.json_path = json_path
        self.image_data = image_data
        self.selected_option = None

        # Set up output directory
        self.output_dir = output_dir
        ensure_dir_exists(output_dir)

        # Flag whether results have been saved
        self.results_saved = False

        # Add evaluation-specific UI elements
        self._add_evaluation_ui()
        
        # Start the evaluation
        self.update_display()

    def _add_evaluation_ui(self) -> None:
        """Add evaluation-specific UI elements."""
        # Add instruction label
        self.instruction_label = ttk.Label(
            self.control_frame,
            text='Select one of the following options to describe the object pointed by the arrow compared to the other one in the image. Please follow your first instinct and note the options change orders for each image.',
            wraplength=self.control_frame.winfo_width()  # Use the actual width of the control panel
        )
        self.instruction_label.pack(anchor=tk.W if not self.is_portrait else tk.CENTER, pady=(5, 0), fill=tk.X)

        # Add binding to update text wrapping
        self.control_frame.bind('<Configure>', self._update_wraplength)

        # Add zoom controls using base class method
        self._add_zoom_controls()

        # Create a frame to hold the option buttons
        self.options_frame = ttk.Frame(self.control_frame)
        self.options_frame.pack(fill=tk.X, pady=10)
        
        # Define the fixed options
        self.options = ["Left", "Small", "Light Gray", "Square"]
        
        # Create buttons for each option
        self.option_buttons = []
        
        # Randomize the order of options
        self.randomized_options = self.options.copy()
        random.shuffle(self.randomized_options)
        
        # Create a button for each option based on interface orientation
        if self.is_portrait:
            # For portrait mode, buttons are stacked vertically
            for option in self.randomized_options:
                btn = ttk.Button(
                    self.options_frame,
                    text=option,
                    command=lambda opt=option: self.handle_option_selection(opt)
                )
                btn.pack(fill=tk.X, pady=5)
                self.option_buttons.append(btn)
        else:
            # For landscape mode, create a 2x2 grid of buttons
            for i, option in enumerate(self.randomized_options):
                row = i // 2
                col = i % 2
                
                # Create a frame for each row to help with layout
                if col == 0:
                    row_frame = ttk.Frame(self.options_frame)
                    row_frame.pack(fill=tk.X, pady=5)
                
                btn = ttk.Button(
                    row_frame,
                    text=option,
                    command=lambda opt=option: self.handle_option_selection(opt)
                )
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                self.option_buttons.append(btn)

        # Create a button frame to hold Save and Continue button
        self.button_frame = ttk.Frame(self.control_frame)
        self.button_frame.pack(fill=tk.X, pady=10)
        
        # Add Save and Continue button (initially disabled)
        self.save_continue_button = ttk.Button(
            self.button_frame,
            text='Save and Continue [Enter]',
            command=self._finish_and_proceed,
            state=tk.DISABLED  # Initially disabled until an option is selected
        )
        self.save_continue_button.pack(fill=tk.X)
        
        # Bind Enter key to save and continue
        self.root.bind('<Return>', lambda event: self._finish_and_proceed() if self.selected_option else None)

        # Update status bar text
        self.update_status('Please select an option for this image, then click "Save and Continue".')

    def update_display(self) -> None:
        """Update the image display."""
        # Update the image display using the base class method
        self.update_image_display()

        # Update the progress label using base class method
        self.update_progress(self.current_position, self.total_images)

        # Reset selected option
        self.selected_option = None
        
        # Re-randomize the options
        self.randomized_options = self.options.copy()
        random.shuffle(self.randomized_options)
        
        # Update button texts with new randomized options
        for i, btn in enumerate(self.option_buttons):
            btn.config(text=self.randomized_options[i], state=tk.NORMAL)
            # Reset command to new option
            btn.config(command=lambda opt=self.randomized_options[i]: self.handle_option_selection(opt))
        
        # Disable save button until option is selected
        self.save_continue_button.config(state=tk.DISABLED)

    def handle_option_selection(self, option: str) -> None:
        """Handle selection of an option.

        Args:
            option: The selected option (Left, Smaller, Lighter, or Square)
        """
        # Store the selected option
        self.selected_option = option
        
        # Update visual state of all buttons
        for btn in self.option_buttons:
            if btn.cget('text') == option or btn.cget('text') == f"{option} ✓":
                # Highlight selected button with checkmark
                btn.config(text=f"{option} ✓")
            else:
                # Remove checkmark from other buttons if present
                original_text = btn.cget('text').replace(" ✓", "")
                btn.config(text=original_text)
            
        # Enable the save and continue button
        self.save_continue_button.config(state=tk.NORMAL)
            
        # Update status bar
        self.update_status(f"You selected '{option}'. You can change your selection or click 'Save and Continue' to proceed to the next image.")

    def _finish_and_proceed(self) -> None:
        """Finish the current evaluation and proceed to the next image."""
        # Ensure an option is selected
        if not self.selected_option:
            return
            
        # Save results
        self._save_results()
        
        # Destroy the main window
        self.root.destroy()
        
        # Call the callback function if provided
        if self.on_complete_callback:
            self.on_complete_callback()

    def _save_results(self) -> None:
        """Save the evaluation results to a JSON file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Use image ID as part of the filename
        image_id = self.image_data.get('image_id', os.path.splitext(os.path.basename(self.image_path))[0])
        filename = f'{self.output_dir}/selection_{image_id}.json'
        
        eval_item = {
            'selected_option': self.selected_option,
            'timestamp': timestamp
        }
        
        # Create results dictionary
        result = {
            'sample_data': self.image_data,
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
            
        # If no selection has been made, warn user
        if self.selected_option is None:
            if not messagebox.askyesno('Data Loss Warning', 
                                     f"You haven't made a selection for this image. Data for this image will be lost.\n\nAre you sure you want to close the window?"):
                # User chose not to close window, continue
                return
        # If selection made but not saved
        elif not self.results_saved:
            if not messagebox.askyesno('Data Loss Warning', 
                                     f"You've made a selection but haven't saved it. Data for this image will be lost.\n\nAre you sure you want to close the window?"):
                # User chose not to close window, continue
                return
        
        # User confirmed close
        if messagebox.askyesno('Confirm Close', 'Are you sure you want to close? No more images will be shown after closing.'):
            # Destroy window
            self.root.destroy()
            
            # Call the callback function if provided
            if self.on_complete_callback:
                self.on_complete_callback(cancelled=True)  # Pass cancelled flag to callback function

    def _update_wraplength(self, event=None) -> None:
        """Update text wrapping for the instruction label."""
        if hasattr(self, 'instruction_label') and self.instruction_label.winfo_exists():
            # Leave some margin (adjust as needed)
            width = self.control_frame.winfo_width() - 20
            if width > 10:  # Ensure positive width
                self.instruction_label.configure(wraplength=width)


class BatchEvaluator:
    """A class for batch evaluation of images with fixed selection options."""
    
    def __init__(self, 
                 json_path: str, 
                 image_dir: str,
                 output_dir: str,
                 max_samples: Optional[int] = None) -> None:
        """Initialize the batch evaluator.
        
        Args:
            json_path: Path to the JSON file with image data.
            image_dir: Directory containing the images.
            output_dir: Directory to save the evaluation results.
            max_samples: Maximum number of samples to process. If None, processes all.
        """
        self.json_path = json_path
        self.image_dir = image_dir
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

        # Add flag to control whether to continue processing
        self.should_continue = True
        
    def _find_starting_index(self) -> int:
        """Find the index from which to start evaluation.
        
        Checks the output directory for existing result files to determine
        where to resume evaluation.
        
        Returns:
            The index to start evaluation from.
        """
        # If output directory doesn't exist, start from beginning
        if not os.path.exists(self.output_dir):
            return 0
            
        # Get all result files in the output directory
        result_files = [f for f in os.listdir(self.output_dir) if f.endswith('.json')]
        
        # If no result files, start from beginning
        if not result_files:
            return 0
            
        # Extract the image ID for each result file and track completed images
        completed_images = set()
        for result_file in result_files:
            arrowed_image_path = result_file.replace('.json', '').replace('selection_', '')
            completed_images.add(arrowed_image_path)
        logger.info(f'Completed images: {completed_images}')
        
        # Check each data item to see if its image has been evaluated
        for i, item in enumerate(self.data_items):
            arrowed_image_path = item.get('arrowed_image_path', '').replace('.png', '')
            # Check if this image is not in the completed list
            if arrowed_image_path and arrowed_image_path not in completed_images:
                logger.info(f'Continue from index {i} (image: {arrowed_image_path})')
                return i
                
        # If all images have been evaluated, return the list length
        return len(self.data_items)
        
    def run(self) -> None:
        """Start the batch evaluation process."""
        if not self.data_items:
            logger.warning('No data items found in the specified JSON file.')
            return
            
        if self.current_index >= len(self.data_items):
            logger.info('All images have been evaluated. Nothing to do.')
            return
            
        logger.info(f'Starting from image {self.current_index + 1}/{self.total_samples}')
        self._process_all_items()
        
    def _process_all_items(self) -> None:
        """Process all data items in the list."""
        while self.current_index < len(self.data_items) and self.should_continue:
            try:
                # Get the current data item
                data_item = self.data_items[self.current_index]
                
                # Get image path from data or construct it      
                if 'arrowed_image_path' in data_item and os.path.exists(os.path.join(self.image_dir, data_item['arrowed_image_path'])):
                    image_path = os.path.join(self.image_dir, data_item['arrowed_image_path'])
                else:
                    # Fallback to constructing path from image_id
                    image_id = data_item.get('image_id')
                    if not image_id:
                        logger.error(f'Processing item {self.current_index} has no image_id field')
                        # Terminate the entire process when an error occurs
                        self.should_continue = False
                        return
                    image_path = os.path.join(self.image_dir, f'{image_id}.jpg')        
                
                logger.info(f'Processing file {self.current_index + 1}/{self.total_samples}: {data_item.get("image_id", "unknown")}')
                logger.info(f'Image path: {image_path}')

                # Create a temporary root window for non-initial items
                if self.current_index > 0:
                    temp_root = tk.Tk()
                    temp_root.destroy()
                    
                # Create a new SelectionEvaluator instance with position information
                app = SelectionEvaluator(
                    image_path=image_path,
                    json_path=self.json_path,
                    image_data=data_item,
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
                # Terminate the entire process when an error occurs
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


def main() -> None:
    """Parse command-line arguments and run the selection evaluator.

    Handles argument parsing and initializes the SelectionEvaluator with
    the provided parameters.
    """
    parser = argparse.ArgumentParser(description='Evaluate images with fixed selection options.')
    parser.add_argument('--json_path', type=str, help='Path to the JSON file containing image data')
    parser.add_argument('--image_dir', type=str, help='Directory containing images')
    parser.add_argument('--output_dir', type=str, help='Directory to save evaluation results')
    parser.add_argument('--max_samples', type=int, default=None,
    help='Maximum number of samples to process in batch mode')

    args = parser.parse_args()

    # Check if required arguments are provided
    if args.json_path and args.image_dir:
        # Batch mode
        batch_evaluator = BatchEvaluator(
            json_path=args.json_path,
            image_dir=args.image_dir,
            output_dir=args.output_dir,
            max_samples=args.max_samples
        )
        batch_evaluator.run()
        return
    else:
        logger.error('Missing required parameters. Please provide --json_path and --image_dir.')
        parser.print_help()
        return


if __name__ == '__main__':
    main() 