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


# Initialize pygame before any other code
pygame.init()
pygame.font.init()


class PixelDescriptionCollector:
    """
    A class for collecting textual descriptions of pixel locations in an image.
    
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
        # Initialize pygame
        pygame.init()
        pygame.font.init()
        
        # Enable key repeat for typing
        pygame.key.set_repeat(500, 50)  # Initial delay, repeat delay
        
        # Load the image
        self.image = pygame.image.load(image_path)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.width, self.height = self.image.get_size()
        
        # Set scaling factor for display
        self.scale_factor = initial_scale
        
        # Calculate window dimensions with input area
        self.window_width = int(self.width * self.scale_factor)
        self.window_height = int(self.height * self.scale_factor) + 200
        
        # Create screen
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption('Pixel Description Collector - Press +/- to resize')
        
        # Set up fonts
        self.font = pygame.font.SysFont('Arial', 18)
        self.large_font = pygame.font.SysFont('Arial', 24)
        
        # Parameters
        self.num_pixels = num_pixels
        self.current_pixel = 0
        self.pixels_marked: List[Tuple[int, int]] = []
        self.descriptions: List[str] = []
        self.current_text = ''
        
        # Directly start with text editing active (focused)
        self.text_active = True
        self.cursor_visible = True
        self.cursor_time = pygame.time.get_ticks()
        
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
    
    def _update_window_size(self) -> None:
        """Update window size based on current scale factor."""
        self.window_width = int(self.width * self.scale_factor)
        self.window_height = int(self.height * self.scale_factor) + 200
        self.screen = pygame.display.set_mode(
            (self.window_width, self.window_height), 
            pygame.RESIZABLE
        )
    
    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """Wrap text to fit within a maximum width.
        
        Args:
            text: The text to wrap.
            max_width: The maximum width in pixels.
            
        Returns:
            A list of lines, each fitting within max_width.
        """
        if not text:
            return ['']
            
        words = text.split(' ')
        lines = []
        current_line = ''
        
        for word in words:
            test_line = current_line + word + ' '
            # Get the width of the test line
            width = self.font.size(test_line)[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word + ' '
                else:
                    # If a single word is too long for a line
                    lines.append(word + ' ')
                    current_line = ''
        
        if current_line:
            lines.append(current_line)
            
        # Remove trailing spaces
        return [line.rstrip() for line in lines]
        
    def run(self) -> None:
        """Main loop to run the interface.
        
        Handles events, updates the interface, and manages the pixel description
        collection workflow until the target number of descriptions is reached.
        """
        running = True
        clock = pygame.time.Clock()
        
        # Print debug info to console
        print("Starting pixel description collector. Instructions:")
        print("- Type your description in the text box")
        print("- Press ENTER to submit and move to the next pixel")
        print("- Press ESCAPE to exit")
        print("- Press HOME/END to navigate text")
        print("- Press BACKSPACE to delete characters")
        
        while running:
            # Clear events at the start of each frame - prevents event buildup
            current_events = pygame.event.get()
            
            for event in current_events:
                # Handle quitting
                if event.type == pygame.QUIT:
                    self._save_data()
                    running = False
                    pygame.quit()
                    sys.exit()
                
                # Handle window resizing
                elif event.type == pygame.VIDEORESIZE:
                    new_width, new_height = event.size
                    # Adjust scale factor based on new window width
                    if self.width > 0:  # Avoid division by zero
                        self.scale_factor = (new_width / self.width)
                    # Update window size
                    self.window_width = new_width
                    self.window_height = new_height
                    self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
                
                # Handle mouse clicks for text input activation
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Get input box rect
                    scaled_height = int(self.height * self.scale_factor)
                    current_width = self.screen.get_size()[0]
                    input_box_rect = pygame.Rect(20, scaled_height + 80, current_width - 40, 80)
                    
                    # Check if mouse clicked in the input box
                    if input_box_rect.collidepoint(event.pos):
                        self.text_active = True
                    else:
                        # Keep active anyway - makes it easier to use
                        self.text_active = True
                
                # Handle keyboard input
                elif event.type == pygame.KEYDOWN:
                    # Debug output to terminal
                    print(f"Key pressed: {pygame.key.name(event.key)} (Unicode: {repr(event.unicode)})")
                    
                    # Always handle +/- for scaling regardless of text focus
                    if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        self.scale_factor += 0.1
                        self._update_window_size()
                        print(f"Scale increased to: {self.scale_factor:.1f}")
                    elif event.key == pygame.K_MINUS:
                        if self.scale_factor > 0.3:  # Don't allow too small
                            self.scale_factor -= 0.1
                            self._update_window_size()
                            print(f"Scale decreased to: {self.scale_factor:.1f}")
                    
                    # Handle text input when text box is active
                    if self.text_active:
                        if event.key == pygame.K_RETURN:
                            # Store description and move to next pixel
                            if self.current_text:
                                print(f"Saving description: '{self.current_text}'")
                                self.descriptions.append(self.current_text)
                                self.current_text = ''
                                self.current_pixel += 1
                                
                                # Check if we've collected enough descriptions
                                if self.current_pixel >= self.num_pixels:
                                    self._save_data()
                                    print("All descriptions collected! Exiting.")
                                    running = False
                                else:
                                    self._generate_random_pixel()
                                    print(f"Moving to pixel {self.current_pixel + 1} of {self.num_pixels}")
                        elif event.key == pygame.K_ESCAPE:
                            print("Escape pressed. Exiting...")
                            self._save_data()
                            running = False
                        elif event.key == pygame.K_BACKSPACE:
                            self.current_text = self.current_text[:-1]
                        elif event.key == pygame.K_TAB:
                            self.current_text += '    '
                        # Ignore control keys and function keys
                        elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL, 
                                          pygame.K_LALT, pygame.K_RALT, 
                                          pygame.K_LSHIFT, pygame.K_RSHIFT,
                                          pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4,
                                          pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8,
                                          pygame.K_F9, pygame.K_F10, pygame.K_F11, pygame.K_F12):
                            pass
                        else:
                            # Add printable character
                            if event.unicode and ord(event.unicode) >= 32:
                                self.current_text += event.unicode
                                print(f"Current text: '{self.current_text}'")
            
            # Update cursor blinking
            current_time = pygame.time.get_ticks()
            if current_time - self.cursor_time > 500:  # 500ms blink rate
                self.cursor_visible = not self.cursor_visible
                self.cursor_time = current_time
            
            # Update cursor appearance based on mouse position
            scaled_height = int(self.height * self.scale_factor)
            current_width = self.screen.get_size()[0]
            input_box_rect = pygame.Rect(20, scaled_height + 80, current_width - 40, 80)
            
            if input_box_rect.collidepoint(pygame.mouse.get_pos()):
                try:
                    # Try to set system cursor
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_IBEAM)
                except:
                    # If system cursor not available, fallback to default
                    pass
            else:
                try:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                except:
                    pass
            
            # Draw the interface
            self._draw()
            pygame.display.flip()
            clock.tick(60)  # Limit to 60 FPS
            
    def _draw(self) -> None:
        """Draw the interface with image and text input.
        
        Renders the current state of the interface, including the image,
        marked pixel, text input area, and instructions.
        """
        # Clear the screen
        self.screen.fill((240, 240, 240))
        
        # Get the current window size
        current_width, current_height = self.screen.get_size()
        scaled_height = int(self.height * self.scale_factor)
        
        # Scale the image while maintaining aspect ratio
        scaled_image = pygame.transform.scale(
            self.image, 
            (int(self.width * self.scale_factor), scaled_height)
        )
        
        # Draw the image
        self.screen.blit(scaled_image, (0, 0))
        
        # Draw the current pixel marker (red dot)
        if self.current_pixel < len(self.pixels_marked):
            x, y = self.pixels_marked[self.current_pixel]
            # Scale the pixel coordinates
            scaled_x = int(x * self.scale_factor)
            scaled_y = int(y * self.scale_factor)
            # Draw a more visible marker
            pygame.draw.circle(self.screen, (255, 0, 0), (scaled_x, scaled_y), 7)
            pygame.draw.circle(self.screen, (255, 255, 255), (scaled_x, scaled_y), 3)
        
        # Draw the text input area background
        pygame.draw.rect(self.screen, (200, 200, 200), (0, scaled_height, current_width, 200))
        
        # Draw the progress information
        progress_text = f'Pixel {self.current_pixel + 1} of {self.num_pixels}'
        progress_surface = self.large_font.render(progress_text, True, (0, 0, 0))
        self.screen.blit(progress_surface, (20, scaled_height + 15))
        
        # Draw the instruction
        instruction = 'Please describe the location of the red pixel so another person can find it:'
        instruction_surface = self.font.render(instruction, True, (0, 0, 0))
        self.screen.blit(instruction_surface, (20, scaled_height + 50))
        
        # Draw the text input box
        input_box_rect = pygame.Rect(20, scaled_height + 80, current_width - 40, 80)
        box_color = (240, 240, 255) if self.text_active else (255, 255, 255)
        border_color = (0, 120, 215) if self.text_active else (169, 169, 169)
        
        # Draw box background and border
        pygame.draw.rect(self.screen, box_color, input_box_rect)
        pygame.draw.rect(self.screen, border_color, input_box_rect, 2 if self.text_active else 1)
        
        # Draw wrapped text
        if self.current_text:
            wrapped_text = self._wrap_text(self.current_text, input_box_rect.width - 20)
            
            for i, line in enumerate(wrapped_text):
                text_surface = self.font.render(line, True, (0, 0, 0))
                y_position = input_box_rect.y + 10 + (i * self.font.get_height())
                self.screen.blit(text_surface, (input_box_rect.x + 10, y_position))
                
                # Only show cursor on the last line
                if i == len(wrapped_text) - 1 and self.text_active and self.cursor_visible:
                    cursor_x = input_box_rect.x + 10 + self.font.size(line)[0]
                    cursor_y = y_position
                    pygame.draw.line(
                        self.screen,
                        (0, 0, 0),
                        (cursor_x, cursor_y),
                        (cursor_x, cursor_y + self.font.get_height()),
                        2
                    )
        else:
            # Show cursor at beginning if text is empty
            if self.text_active and self.cursor_visible:
                pygame.draw.line(
                    self.screen,
                    (0, 0, 0),
                    (input_box_rect.x + 10, input_box_rect.y + 10),
                    (input_box_rect.x + 10, input_box_rect.y + 10 + self.font.get_height()),
                    2
                )
        
        # Draw the submit instruction
        submit_text = 'Press Enter to submit and continue'
        submit_surface = self.font.render(submit_text, True, (80, 80, 80))
        self.screen.blit(submit_surface, (20, scaled_height + 170))


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
