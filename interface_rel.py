"""Pixel Description Evaluator.

This tool evaluates how well descriptions of pixel locations can be understood by others.
It loads previously collected pixel descriptions and their associated image,
displays each description to users, and asks them to click on where they think the pixel is.
The tool records the guessed locations and calculates the accuracy (L2 distance) from the true locations.

Usage:
    python pixel_description_evaluator.py json_file image_path [--output_dir output]
"""

import argparse
import json
import math
import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageTk

ACC_MAX_DIST = 50


class PixelDescriptionEvaluator:
    """A class for evaluating how well pixel descriptions can be understood.

    This class loads previously saved pixel descriptions, shows them to users,
    and asks users to click on where they think the described pixel is located.
    It then calculates and records the accuracy of these guesses.
    """
    def __init__(self, json_path: str, image_path: str, output_dir: str = 'output') -> None:
        """Initialize the evaluator with a JSON file of descriptions and an image.

        Args:
            json_path: Path to the JSON file containing pixel descriptions.
            image_path: Path to the image file referenced in the descriptions.
            output_dir: Directory to save the evaluation results. Defaults to 'output'.
        """
        # Load the JSON data
        with open(json_path, 'r') as f:
            self.data = json.load(f)

        self.json_path = json_path
        self.json_name = os.path.basename(json_path)

        # Load the image
        self.original_image = Image.open(image_path)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.width, self.height = self.original_image.size

        # Verify the image dimensions match the JSON data
        if tuple(self.data['image_dimensions']) != (self.width, self.height):
            print("Warning: Image dimensions in JSON don't match the loaded image.")

        # Set up evaluation tracking
        self.pixel_data = self.data['pixel_data']
        self.current_index = 0
        self.total_pixels = len(self.pixel_data)
        self.guesses: List[Tuple[int, int]] = []
        self.distances: List[float] = []

        # Set up output directory
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Set scaling factor for display
        self.scale_factor = 1.0

        # Set up the main window
        self.root = tk.Tk()
        self.root.title(f'Pixel Description Evaluator - {self.image_name}')

        # Calculate initial window size
        self.scaled_width = int(self.width * self.scale_factor)
        self.scaled_height = int(self.height * self.scale_factor)

        # Configure window
        self.root.geometry(f'{self.scaled_width + 40}x{self.scaled_height + 200}')
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        # Create frame for the image
        self.image_frame = ttk.Frame(self.root)
        self.image_frame.pack(pady=10)

        # Create label for the image and bind click event
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack()
        self.image_label.bind('<Button-1>', self.handle_click)

        # Create frame for controls
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(fill=tk.X, padx=20, pady=10)

        # Add progress label
        self.progress_label = ttk.Label(
            self.control_frame,
            text=f'Evaluating description {self.current_index + 1} of {self.total_pixels}',
            font=('Arial', 12, 'bold')
        )
        self.progress_label.pack(anchor=tk.W)

        # Add instruction label
        self.instruction_label = ttk.Label(
            self.control_frame,
            text='Read the description below and click on the image where you think the pixel is located:',
            wraplength=self.scaled_width
        )
        self.instruction_label.pack(anchor=tk.W, pady=(5, 0))

        # Add description display area
        self.description_display = scrolledtext.ScrolledText(
            self.control_frame,
            height=4,
            width=50,
            wrap=tk.WORD,
            font=('Arial', 11)
        )
        self.description_display.pack(fill=tk.X, pady=5)
        self.description_display.configure(state='disabled')  # Read-only

        # Add zoom controls
        self.zoom_frame = ttk.Frame(self.control_frame)
        self.zoom_frame.pack(fill=tk.X, pady=5)

        self.zoom_out_button = ttk.Button(
            self.zoom_frame,
            text='Zoom Out (-)',
            command=self.zoom_out
        )
        self.zoom_out_button.pack(side=tk.LEFT)

        self.zoom_in_button = ttk.Button(
            self.zoom_frame,
            text='Zoom In (+)',
            command=self.zoom_in
        )
        self.zoom_in_button.pack(side=tk.LEFT, padx=5)

        self.scale_label = ttk.Label(
            self.zoom_frame,
            text=f'Scale: {self.scale_factor:.1f}x'
        )
        self.scale_label.pack(side=tk.LEFT, padx=5)

        # Add undo button (if user wants to redo their guess)
        self.undo_button = ttk.Button(
            self.zoom_frame,
            text='Undo Last Guess',
            command=self.undo_last_guess,
            state='disabled'  # Initially disabled
        )
        self.undo_button.pack(side=tk.RIGHT)

        # Status bar at the bottom
        self.status_bar = ttk.Label(
            self.root,
            text='Click on the image where you think the described pixel is located.',
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind events
        self.root.bind('<plus>', lambda e: self.zoom_in())
        self.root.bind('<equal>', lambda e: self.zoom_in())
        self.root.bind('<minus>', lambda e: self.zoom_out())
        self.root.bind('<Escape>', lambda e: self.on_closing())

        # Start the evaluation with the first description
        self.update_display()

    def update_display(self) -> None:
        """Update the image display and description text."""
        # Display the original image (without any markers)
        image_copy = self.original_image.copy()

        # Resize the image according to scale factor
        scaled_image = image_copy.resize(
            (int(self.width * self.scale_factor),
             int(self.height * self.scale_factor)),
            Image.Resampling.LANCZOS
        )

        # Convert to PhotoImage and update the label
        self.photo_image = ImageTk.PhotoImage(scaled_image)
        self.image_label.configure(image=self.photo_image)

        # Update the progress label
        self.progress_label.configure(
            text=f'Evaluating description {self.current_index + 1} of {self.total_pixels}'
        )

        # Update the description text
        current_description = self.pixel_data[self.current_index]['description']
        self.description_display.configure(state='normal')
        self.description_display.delete('1.0', tk.END)
        self.description_display.insert('1.0', current_description)
        self.description_display.configure(state='disabled')

        # Update scale label
        self.scale_label.configure(text=f'Scale: {self.scale_factor:.1f}x')

        # Update window size to fit the scaled image
        self.scaled_width = int(self.width * self.scale_factor)
        self.scaled_height = int(self.height * self.scale_factor)
        self.root.geometry(f'{self.scaled_width + 40}x{self.scaled_height + 200}')

    def handle_click(self, event: tk.Event) -> None:
        """Handle mouse click on the image to record the guessed pixel location.

        Args:
            event: The Tkinter event containing click coordinates.
        """
        # Convert the scaled coordinates back to original image coordinates
        if self.scale_factor > 0:  # Avoid division by zero
            original_x = int(event.x / self.scale_factor)
            original_y = int(event.y / self.scale_factor)
        else:
            original_x, original_y = event.x, event.y

        # Make sure coordinates are within image bounds
        original_x = max(0, min(original_x, self.width - 1))
        original_y = max(0, min(original_y, self.height - 1))

        # Get the true location for this pixel
        true_location = tuple(self.pixel_data[self.current_index]['pixel_position'])

        # Calculate the L2 distance (Euclidean distance)
        distance = math.sqrt(
            (original_x - true_location[0])**2 +
            (original_y - true_location[1])**2
        )

        # Store the guess and distance
        self.guesses.append((original_x, original_y))
        self.distances.append(distance)

        # Show the true location and the guessed location
        self.show_comparison(true_location, (original_x, original_y), distance)
        self.undo_button.configure(state='normal')

    def show_comparison(self, true_loc: Tuple[int, int], guess_loc: Tuple[int, int], distance: float) -> None:
        """Show a comparison between the true location and the guessed location.

        Args:
            true_loc: The true pixel coordinates (x, y).
            guess_loc: The guessed pixel coordinates (x, y).
            distance: The L2 distance between the true and guessed locations.
        """
        # Create a copy of the original image
        image_copy = self.original_image.copy()
        draw = ImageDraw.Draw(image_copy)

        # Draw the true location as a green dot
        marker_radius = max(5, int(self.scale_factor * 3))
        draw.ellipse(
            [(true_loc[0] - marker_radius, true_loc[1] - marker_radius),
             (true_loc[0] + marker_radius, true_loc[1] + marker_radius)],
            fill='green',
            outline='white'
        )

        # Draw the guessed location as a blue dot
        draw.ellipse(
            [(guess_loc[0] - marker_radius, guess_loc[1] - marker_radius),
             (guess_loc[0] + marker_radius, guess_loc[1] + marker_radius)],
            fill='blue',
            outline='white'
        )

        # Draw a line connecting them
        draw.line([true_loc, guess_loc], fill='red', width=2)

        # Resize the image according to scale factor
        scaled_image = image_copy.resize(
            (int(self.width * self.scale_factor),
             int(self.height * self.scale_factor)),
            Image.Resampling.LANCZOS
        )

        # Convert to PhotoImage and update the label
        self.photo_image = ImageTk.PhotoImage(scaled_image)
        self.image_label.configure(image=self.photo_image)

        # Update status bar with the distance
        self.status_bar.configure(
            text=f"Your guess was {distance:.2f} pixels away from the true location. Click 'Next' to continue."
        )

        # Replace the image click binding with the next button
        self.image_label.unbind('<Button-1>')

        # Add a 'Next' button to continue
        self.next_button = ttk.Button(
            self.control_frame,
            text='Next Description',
            command=self.next_description
        )
        self.next_button.pack(pady=10)

    def next_description(self) -> None:
        """Move to the next description."""
        # Remove the next button
        if hasattr(self, 'next_button'):
            self.next_button.destroy()

        # Move to the next index
        self.current_index += 1

        # Check if we've gone through all descriptions
        if self.current_index >= self.total_pixels:
            self._save_results()
            self.show_results()
        else:
            # Rebind the click event and update display
            self.image_label.bind('<Button-1>', self.handle_click)
            self.update_display()
            self.status_bar.configure(
                text='Click on the image where you think the described pixel is located.'
            )
            self.undo_button.configure(state='disabled')

    def undo_last_guess(self) -> None:
        """Allow the user to undo their last guess and try again."""
        # Only allow undo before moving to next description
        if hasattr(self, 'next_button'):
            messagebox.showinfo('Cannot Undo', 'Cannot undo after viewing the true location.')
            return

        if self.guesses:
            # Remove the last guess and distance
            self.guesses.pop()
            self.distances.pop()

            # Update the display
            self.update_display()
            self.status_bar.configure(
                text='Previous guess removed. Click on the image again.'
            )
            self.undo_button.configure(state='disabled')

    def zoom_in(self) -> None:
        """Increase the zoom level."""
        self.scale_factor += 0.1
        self.update_display()

    def zoom_out(self) -> None:
        """Decrease the zoom level."""
        if self.scale_factor > 0.3:  # Don't allow too small
            self.scale_factor -= 0.1
            self.update_display()

    def _save_results(self) -> None:
        """Save the evaluation results to a JSON file.

        Creates a timestamped JSON file containing all the true pixel positions,
        guessed positions, and calculated distances.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{self.output_dir}/rel_{self.image_name[:-4]}_{timestamp}.json'

        # Calculate accuracy statistics
        average_distance = sum(self.distances) / len(self.distances) if self.distances else 0
        max_distance = max(self.distances) if self.distances else 0
        min_distance = min(self.distances) if self.distances else 0

        # Count 'accurate' guesses (within 50 pixels)
        accurate_guesses = sum(1 for dist in self.distances if dist <= ACC_MAX_DIST)
        accuracy_rate = accurate_guesses / len(self.distances) if self.distances else 0

        results: Dict[str, Any] = {
            'image_path': self.image_path,
            'json_path': self.json_path,
            'image_dimensions': (self.width, self.height),
            'statistics': {
                'average_distance': average_distance,
                'max_distance': max_distance,
                'min_distance': min_distance,
                'accuracy_rate': accuracy_rate,
                'accurate_guesses': accurate_guesses,
                'total_guesses': len(self.distances)
            },
            'evaluation_data': [
                {
                    'description': self.pixel_data[i]['description'],
                    'true_position': self.pixel_data[i]['pixel_position'],
                    'guessed_position': self.guesses[i],
                    'distance': self.distances[i]
                }
                for i in range(len(self.guesses))
            ]
        }

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)

        print(f'Evaluation results saved to {filename}')
        self.results_filename = filename

    def show_results(self) -> None:
        """Show a summary of the evaluation results."""
        # Calculate accuracy statistics
        average_distance = sum(self.distances) / len(self.distances) if self.distances else 0
        max_distance = max(self.distances) if self.distances else 0
        min_distance = min(self.distances) if self.distances else 0

        # Count 'accurate' guesses (within 50 pixels)
        accurate_guesses = sum(1 for dist in self.distances if dist <= ACC_MAX_DIST)
        accuracy_rate = accurate_guesses / len(self.distances) if self.distances else 0

        # Create a new window for results
        results_window = tk.Toplevel(self.root)
        results_window.title('Evaluation Results')
        results_window.geometry('500x400')

        # Add a results frame
        results_frame = ttk.Frame(results_window, padding=20)
        results_frame.pack(fill=tk.BOTH, expand=True)

        # Add a title
        title_label = ttk.Label(
            results_frame,
            text='Pixel Description Evaluation Results',
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 20))

        # Add statistics
        stats_frame = ttk.Frame(results_frame)
        stats_frame.pack(fill=tk.X, pady=10)

        # Create a formatted text area for results
        results_text = scrolledtext.ScrolledText(
            stats_frame,
            height=15,
            width=50,
            wrap=tk.WORD,
            font=('Arial', 11)
        )
        results_text.pack(fill=tk.BOTH, expand=True)

        # Add the statistics to the text area
        results_text.insert(tk.END, f'Image: {self.image_name}\n\n')
        results_text.insert(tk.END, f'Total descriptions evaluated: {len(self.distances)}\n\n')
        results_text.insert(tk.END, f'Average distance: {average_distance:.2f} pixels\n')
        results_text.insert(tk.END, f'Maximum distance: {max_distance:.2f} pixels\n')
        results_text.insert(tk.END, f'Minimum distance: {min_distance:.2f} pixels\n\n')
        results_text.insert(tk.END, f'Accurate guesses (within {ACC_MAX_DIST} pixels): {accurate_guesses}\n')
        results_text.insert(tk.END, f'Accuracy rate: {accuracy_rate:.2%}\n\n')
        results_text.insert(tk.END, f'Results saved to:\n{self.results_filename}\n')

        results_text.configure(state='disabled')  # Make read-only

        # Add close button
        close_button = ttk.Button(
            results_frame,
            text='Close',
            command=self.root.destroy
        )
        close_button.pack(pady=10)

        # Disable the main window until results are closed
        results_window.transient(self.root)
        results_window.grab_set()
        self.root.wait_window(results_window)

    def on_closing(self) -> None:
        """Handle window closing event."""
        if self.current_index > 0 and self.current_index < self.total_pixels:
            if messagebox.askyesno('Save Partial Results',
                                   "You haven\'t completed all descriptions. Save partial results?"):
                self._save_results()
        elif self.current_index >= self.total_pixels and not hasattr(self, 'results_filename'):
            self._save_results()

        self.root.destroy()

    def run(self) -> None:
        """Run the main application loop."""
        self.root.mainloop()


def main() -> None:
    """Parse command-line arguments and run the pixel description evaluator.

    Handles argument parsing and initializes the PixelDescriptionEvaluator with
    the provided parameters.
    """
    parser = argparse.ArgumentParser(description='Evaluate pixel location descriptions.')
    parser.add_argument('--json_path', type=str, default='./example/gpt4o_reg.json',
                        help='Path to the JSON file with pixel descriptions')
    parser.add_argument('--image_path', type=str, default='./example/example.jpg',
                        help='Path to the image file')
    parser.add_argument('--output_dir', type=str, default='output',
                        help='Directory to save the evaluation results (default: output)')

    args = parser.parse_args()

    evaluator = PixelDescriptionEvaluator(
        json_path=args.json_path,
        image_path=args.image_path,
        output_dir=args.output_dir
    )

    evaluator.run()


if __name__ == '__main__':
    main()
