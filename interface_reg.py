"""Pixel-level Referring Expression Annotation Interface.

A tool for collecting human-written descriptions of pixel locations in an image.
This script displays an interface with an image where random pixels are marked with a red dot.
Users are asked to provide textual descriptions of these marked pixels.
The descriptions are collected and saved to a JSON file for later use.

Usage:
    python interface_reg.py path/to/image.jpg [--num_pixels 3] [--output_dir collected_descriptions]
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk, ImageDraw
import random
import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional


class PixelDescriptionCollector:
    """A class for collecting textual descriptions of pixel locations in an image.
    
    This class creates a graphical interface that displays an image and marks
    random pixels with a red dot. It prompts the user to describe the location
    of each marked pixel and collects these descriptions for later use.
    """
    
    def __init__(self, image_path: str, num_pixels: int = 20, output_dir: str = 'collected_descriptions',
                 initial_scale: float = 1.0) -> None:
        """Initialize PixelDescriptionCollector with image and collection parameters.
        
        Args:
            image_path: Path to the image file to be used.
            num_pixels: Number of pixel descriptions to collect. Defaults to 20.
            output_dir: Directory to save the collected descriptions. Defaults to 'collected_descriptions'.
            initial_scale: Initial scale factor for the display. Defaults to 1.0.
        """
        # Load the image using PIL
        self.original_image = Image.open(image_path)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.width, self.height = self.original_image.size
        
        # Set scaling factor for display
        self.scale_factor = initial_scale
        
        # Parameters
        self.num_pixels = num_pixels
        self.current_pixel = 0
        self.pixels_marked: List[Tuple[int, int]] = []
        self.descriptions: List[str] = []
        
        # Create output directory if it doesn't exist
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Set up the main window
        self.root = tk.Tk()
        self.root.title(f"Pixel Description Collector - {self.image_name}")
        
        # Calculate initial window size
        self.scaled_width = int(self.width * self.scale_factor)
        self.scaled_height = int(self.height * self.scale_factor)
        
        # Configure window
        self.root.geometry(f"{self.scaled_width + 40}x{self.scaled_height + 200}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Create frame for the image
        self.image_frame = ttk.Frame(self.root)
        self.image_frame.pack(pady=10)
        
        # Create label for the image
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack()
        
        # Create frame for controls
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Add progress label
        self.progress_label = ttk.Label(
            self.control_frame, 
            text=f"Pixel {self.current_pixel + 1} of {self.num_pixels}",
            font=("Arial", 12, "bold")
        )
        self.progress_label.pack(anchor=tk.W)
        
        # Add instruction label
        self.instruction_label = ttk.Label(
            self.control_frame,
            text="Please describe the location of the red pixel so another person can find it:",
            wraplength=self.scaled_width
        )
        self.instruction_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Add text input area
        self.text_input = scrolledtext.ScrolledText(
            self.control_frame,
            height=4,
            width=50,
            wrap=tk.WORD,
            font=("Arial", 11)
        )
        self.text_input.pack(fill=tk.X, pady=5)
        self.text_input.focus_set()
        
        # Add submit button
        self.submit_button = ttk.Button(
            self.control_frame,
            text="Submit & Continue (Enter)",
            command=self.save_description
        )
        self.submit_button.pack(anchor=tk.E, pady=5)
        
        # Add zoom controls
        self.zoom_frame = ttk.Frame(self.control_frame)
        self.zoom_frame.pack(fill=tk.X, pady=5)
        
        self.zoom_out_button = ttk.Button(
            self.zoom_frame,
            text="Zoom Out (-)",
            command=self.zoom_out
        )
        self.zoom_out_button.pack(side=tk.LEFT)
        
        self.zoom_in_button = ttk.Button(
            self.zoom_frame,
            text="Zoom In (+)",
            command=self.zoom_in
        )
        self.zoom_in_button.pack(side=tk.LEFT, padx=5)
        
        self.scale_label = ttk.Label(
            self.zoom_frame,
            text=f"Scale: {self.scale_factor:.1f}x"
        )
        self.scale_label.pack(side=tk.LEFT, padx=5)
        
        # Status bar at the bottom
        self.status_bar = ttk.Label(
            self.root,
            text="Ready. Press Enter to submit after typing your description.",
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind events
        self.text_input.bind("<Return>", self.handle_enter)
        self.root.bind("<plus>", lambda e: self.zoom_in())
        self.root.bind("<equal>", lambda e: self.zoom_in())
        self.root.bind("<minus>", lambda e: self.zoom_out())
        self.root.bind("<Escape>", lambda e: self.on_closing())
        
        # Generate first random pixel
        self._generate_random_pixel()
        self.update_display()
    
    def _generate_random_pixel(self) -> None:
        """Generate a random pixel position that hasn't been used before.
        
        Selects a random (x, y) coordinate within the image dimensions
        and ensures it hasn't been selected before.
        """
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            
            # Check if this pixel was already used
            if (x, y) not in self.pixels_marked:
                self.pixels_marked.append((x, y))
                break
    
    def update_display(self) -> None:
        """Update the image display with the current pixel highlighted."""
        # Start with a copy of the original image
        image_copy = self.original_image.copy()
        draw = ImageDraw.Draw(image_copy)
        
        # Draw the red pixel marker - make it more visible with a circle
        if self.current_pixel < len(self.pixels_marked):
            x, y = self.pixels_marked[self.current_pixel]
            marker_radius = max(5, int(self.scale_factor * 3))
            draw.ellipse(
                [(x - marker_radius, y - marker_radius), 
                 (x + marker_radius, y + marker_radius)],
                fill="red",
                outline="white"
            )
        
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
            text=f"Pixel {self.current_pixel + 1} of {self.num_pixels}"
        )
        
        # Update scale label
        self.scale_label.configure(text=f"Scale: {self.scale_factor:.1f}x")
        
        # Update window size to fit the scaled image
        self.scaled_width = int(self.width * self.scale_factor)
        self.scaled_height = int(self.height * self.scale_factor)
        self.root.geometry(f"{self.scaled_width + 40}x{self.scaled_height + 200}")
    
    def handle_enter(self, event: Optional[tk.Event] = None) -> None:
        """Handle Enter key press in the text input."""
        # In some cases, the text widget adds a newline - remove it
        text = self.text_input.get("1.0", "end-1c").rstrip()
        if text:  # Only proceed if there's text
            self.save_description()
            return "break"  # Prevent default Enter behavior
    
    def save_description(self) -> None:
        """Save the current description and move to the next pixel."""
        description = self.text_input.get("1.0", "end-1c").strip()
        
        if not description:
            self.status_bar.configure(
                text="Please enter a description before continuing."
            )
            return
        
        # Save the description
        self.descriptions.append(description)
        self.status_bar.configure(
            text=f"Description saved: '{description[:50]}{'...' if len(description) > 50 else ''}'"
        )
        
        # Clear the text input
        self.text_input.delete("1.0", tk.END)
        
        # Move to the next pixel
        self.current_pixel += 1
        
        # Check if we've collected enough descriptions
        if self.current_pixel >= self.num_pixels:
            self._save_data()
            self.status_bar.configure(
                text=f"All {self.num_pixels} descriptions collected and saved to {self.output_dir}!"
            )
            self.root.after(2000, self.root.destroy)  # Close after 2 seconds
        else:
            self._generate_random_pixel()
            self.update_display()
            self.text_input.focus_set()
    
    def zoom_in(self) -> None:
        """Increase the zoom level."""
        self.scale_factor += 0.1
        self.update_display()
    
    def zoom_out(self) -> None:
        """Decrease the zoom level."""
        if self.scale_factor > 0.3:  # Don't allow too small
            self.scale_factor -= 0.1
            self.update_display()
    
    def _save_data(self) -> None:
        """Save the collected descriptions to a JSON file.
        
        Creates a timestamped JSON file containing all the pixel positions
        and their corresponding descriptions.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{self.output_dir}/pixel_descriptions_{self.image_name}_{timestamp}.json'
        
        data: Dict[str, Any] = {
            'image_path': self.image_path,
            'image_dimensions': (self.width, self.height),
            'pixel_data': [
                {
                    'pixel_position': pixel,
                    'description': description
                }
                for pixel, description in zip(self.pixels_marked, self.descriptions)
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"Data saved to {filename}")
    
    def on_closing(self) -> None:
        """Handle window closing event."""
        if self.descriptions:
            self._save_data()
        self.root.destroy()
    
    def run(self) -> None:
        """Run the main application loop."""
        self.root.mainloop()


def main() -> None:
    """Parse command-line arguments and run the pixel description collector.

    Handles argument parsing and initializes the PixelDescriptionCollector with
    the provided parameters.
    """
    import argparse

    parser = argparse.ArgumentParser(description='Collect referring expressions of pixel locations.')
    parser.add_argument('--image_path', type=str, default='./images/example.jpg',
                        help='Path to the image file')
    parser.add_argument('--num_pixels', type=int, default=3,
                        help='Number of pixels to collect descriptions for (default: 3)')
    parser.add_argument('--output_dir', type=str, default='output',
                        help='Directory to save the collected descriptions (default: output)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Initial scale factor for the display (default: 1.0)')
    
    args = parser.parse_args()
    
    collector = PixelDescriptionCollector(
        image_path=args.image_path,
        num_pixels=args.num_pixels,
        output_dir=args.output_dir,
        initial_scale=args.scale
    )
    collector.run()


if __name__ == '__main__':
    main()
