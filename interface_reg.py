"""Pixel-level Referring Expression Annotation Interface.

A tool for collecting human-written descriptions of pixel locations in an image.
This script displays an interface with an image where random pixels are marked with a red dot.
Users are asked to provide textual descriptions of these marked pixels.
The descriptions are collected and saved to a JSON file for later use.

Usage:
    python interface_reg.py path/to/image.jpg [--num_pixels 3] [--output_dir collected_descriptions]
"""

import json
import os
import random
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pygame


class PixelDescriptionCollector:
    """A class for collecting textual descriptions of pixel locations in an image.

    This class creates a graphical interface that displays an image and marks
    random pixels with a red dot. It prompts the user to describe the location
    of each marked pixel and collects these descriptions for later use.
    """

    def __init__(self, image_path: str, num_pixels: int = 3, output_dir: str = 'output') -> None:
        """Initialize PixelDescriptionCollector with image and collection parameters.

        Args:
            image_path: Path to the image file to be used.
            num_pixels: Number of pixel descriptions to collect. Defaults to 3.
            output_dir: Directory to save the collected descriptions. Defaults to 'output'.
        """
        # Initialize pygame
        pygame.init()
        pygame.font.init()

        # Load the image
        self.image = pygame.image.load(image_path)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.width, self.height = self.image.get_size()

        # Create screen
        self.screen = pygame.display.set_mode((self.width, self.height + 150))
        pygame.display.set_caption('Pixel Description Collector')

        # Set up fonts
        self.font = pygame.font.SysFont('Arial', 18)
        self.large_font = pygame.font.SysFont('Arial', 24)

        # Parameters
        self.num_pixels = num_pixels
        self.current_pixel = 0
        self.pixels_marked: List[Tuple[int, int]] = []
        self.descriptions: List[str] = []
        self.current_text = ''
        self.text_active = True

        # Create output directory if it doesn't exist
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Generate first random pixel
        self._generate_random_pixel()

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

        print(f'Data saved to {filename}')

    def run(self) -> None:
        """Main loop to run the interface.

        Handles events, updates the interface, and manages the pixel description
        collection workflow until the target number of descriptions is reached.
        """
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._save_data()
                    running = False
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if self.text_active:
                        if event.key == pygame.K_RETURN:
                            # Store the description and move to next pixel
                            if self.current_text:
                                self.descriptions.append(self.current_text)
                                self.current_text = ''
                                self.current_pixel += 1

                                # Check if we've collected enough descriptions
                                if self.current_pixel >= self.num_pixels:
                                    self._save_data()
                                    running = False
                                else:
                                    self._generate_random_pixel()
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_text = self.current_text[:-1]
                        else:
                            self.current_text += event.unicode

            # Draw the interface
            self._draw()
            pygame.display.flip()

    def _draw(self) -> None:
        """Draw the interface with image and text input.

        Renders the current state of the interface, including the image,
        marked pixel, text input area, and instructions.
        """
        # Clear the screen
        self.screen.fill((240, 240, 240))

        # Draw the image
        self.screen.blit(self.image, (0, 0))

        # Draw the current pixel marker (red dot)
        if self.current_pixel < len(self.pixels_marked):
            x, y = self.pixels_marked[self.current_pixel]
            pygame.draw.circle(self.screen, (255, 0, 0), (x, y), 5)

        # Draw the text input area background
        pygame.draw.rect(self.screen, (200, 200, 200), (0, self.height, self.width, 150))

        # Draw the progress information
        progress_text = f'Pixel {self.current_pixel + 1} of {self.num_pixels}'
        progress_surface = self.large_font.render(progress_text, True, (0, 0, 0))
        self.screen.blit(progress_surface, (20, self.height + 15))

        # Draw the instruction
        instruction = 'Please describe the location of the red pixel so another person can find it:'
        instruction_surface = self.font.render(instruction, True, (0, 0, 0))
        self.screen.blit(instruction_surface, (20, self.height + 50))

        # Draw the text input
        pygame.draw.rect(self.screen, (255, 255, 255), (20, self.height + 80, self.width - 40, 30))
        text_surface = self.font.render(self.current_text, True, (0, 0, 0))
        self.screen.blit(text_surface, (25, self.height + 85))

        # Draw the submit instruction
        submit_text = 'Press Enter to submit and continue'
        submit_surface = self.font.render(submit_text, True, (80, 80, 80))
        self.screen.blit(submit_surface, (20, self.height + 120))


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

    args = parser.parse_args()

    collector = PixelDescriptionCollector(
        image_path=args.image_path,
        num_pixels=args.num_pixels,
        output_dir=args.output_dir
    )

    collector.run()


if __name__ == '__main__':
    main()
