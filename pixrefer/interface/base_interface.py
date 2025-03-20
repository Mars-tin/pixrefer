"""Base interface for pixel-related applications.

This module provides a base class for pixel-related interfaces with common functionality
such as image display, zooming, and layout configuration.
"""

import os
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from typing import Optional, Callable, Any
from PIL import Image, ImageTk


class BaseInterface:
    """Base class for pixel-related interfaces.
    
    This class provides common functionality for interfaces that work with pixels,
    such as image display, zooming, and basic UI setup.
    """
    
    def __init__(
        self, 
        image_path: str, 
        title: str = 'Pixel Interface',
        initial_scale: float = 0.5,
        on_complete_callback: Optional[Callable[[], None]] = None,
        current_position: Optional[int] = None,
        total_images: Optional[int] = None
    ) -> None:
        """Initialize the base interface with an image.
        
        Args:
            image_path: Path to the image file.
            title: Title for the window. Defaults to 'Pixel Interface'.
            initial_scale: Initial scale factor for the image. Defaults to 0.5.
            on_complete_callback: Function to call when the interface is closed or task is completed.
            current_position: Current position in a batch process (1-based).
            total_images: Total number of images in a batch process.
        """
        # Load the image
        self.original_image = Image.open(image_path)
        self.image_path = image_path
        self.image_name = os.path.basename(image_path)
        self.width, self.height = self.original_image.size
        print(f'Init: width: {self.width}, height: {self.height}')
        
        # Set scaling factor for calculation
        self.scale_factor = initial_scale
        # Set display_scale_factor's default value, which will be updated in _calculate_adaptive_scaling
        self.display_scale_factor = initial_scale
        # Store callback
        self.on_complete_callback = on_complete_callback
        
        # Update title with position information if provided
        if current_position is not None and total_images is not None:
            title += f' ({current_position} / {total_images})'
        
        # Set up the main window
        self.root = tk.Tk()
        # self.root.mainloop()
        self.root.withdraw()  # Hide window initially until positioned
        self.root.title(title)
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Check if image is portrait or landscape
        self.is_portrait = self.height > self.width
        
        # Calculate adaptive scaling to fit screen
        self._calculate_adaptive_scaling()
        
        # Configure main layout
        self._configure_base_layout()
        
        # Create tooltip for zoom limits
        self._create_tooltip()
        
        # Bind common events
        self._bind_common_events()
        
        # Set initial window size based on image and controls
        self._set_initial_window_size()
        
        # Set window close protocol
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        
        # Center window before showing it
        self.root.update_idletasks()  # Ensure all widgets are updated
        self.center_window()
        self.root.deiconify()  # Show window after positioning
    
    def _calculate_adaptive_scaling(self) -> None:
        """Calculate adaptive scaling to fit screen."""
        # Max screen real estate we want to use (80% of screen)
        max_screen_width = int(self.screen_width * 0.8)
        max_screen_height = int(self.screen_height * 0.8)

        # Control panel width (for portrait mode)
        control_panel_width = 300

        if self.is_portrait:
            # For portrait images, we need to leave space on the right for controls
            available_width = max_screen_width - control_panel_width
            scale_w = available_width / self.width
            scale_h = max_screen_height / self.height
            self.scale_factor = min(scale_w, scale_h, 1.0)  # Don't enlarge images beyond original size
            
            # For small portrait images (height less than 500 pixels), automatically adjust display scale to 0.8
            if self.height < 500:
                self.display_scale_factor = 0.8
            
        else:
            # For landscape images, controls will be below the image
            scale_w = max_screen_width / self.width
            scale_h = max_screen_height * 0.7 / self.height  # Leave 30% for controls below
            self.scale_factor = min(scale_w, scale_h, 1.0)  # Don't enlarge images beyond original size
    
    def _configure_base_layout(self) -> None:
        """Configure the base layout based on image orientation."""
        # Calculate the scaled dimensions
        self.scaled_width = int(self.width * self.scale_factor)
        self.scaled_height = int(self.height * self.scale_factor)

        # Create a main container with scrollbars
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbars
        self.h_scrollbar = ttk.Scrollbar(self.main_container, orient=tk.HORIZONTAL)
        self.v_scrollbar = ttk.Scrollbar(self.main_container, orient=tk.VERTICAL)
        
        # Create a canvas for scrolling
        self.canvas = tk.Canvas(self.main_container, 
                               xscrollcommand=self.h_scrollbar.set,
                               yscrollcommand=self.v_scrollbar.set)
        
        # Configure scrollbars
        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)
        
        # Pack scrollbars and canvas
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create a frame inside the canvas for all content
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        
        # Configure canvas to resize with the frame
        self.scrollable_frame.bind('<Configure>', 
                                  lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Set minimum width for control panel to ensure text has enough display space
        control_panel_width = 400

        # Create the main content frame
        self.main_frame = ttk.Frame(self.scrollable_frame)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if self.is_portrait:
            # Create a horizontal layout for portrait images
            # Create left frame for image
            self.image_frame = ttk.Frame(self.main_frame)
            self.image_frame.pack(side=tk.LEFT, padx=(0, 10))
            
            # Create scrollable container for control panel
            self.control_container = ttk.Frame(self.main_frame, width=control_panel_width)
            self.control_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            # Set control panel container's minimum height to 400 pixels
            self.control_container.configure(height=400)
            self.control_container.pack_propagate(False)  # Prevent shrinking
            
            # Create canvas and scrollbar
            self.control_canvas = tk.Canvas(self.control_container)
            self.control_scrollbar = ttk.Scrollbar(
                self.control_container, 
                orient=tk.VERTICAL, 
                command=self.control_canvas.yview
            )
            
            # Configure canvas
            self.control_canvas.configure(yscrollcommand=self.control_scrollbar.set)
            self.control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # Set initial height for canvas to match container
            self.control_canvas.configure(height=400)
            self.control_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Create control panel in canvas
            self.control_frame = ttk.Frame(self.control_canvas)
            self.control_canvas_frame = self.control_canvas.create_window(
                (0, 0), 
                window=self.control_frame, 
                anchor='nw', 
                width=control_panel_width-20  # Subtract scrollbar width
            )
            
            # Configure control panel scroll region
            self.control_frame.bind(
                '<Configure>', 
                lambda e: self.control_canvas.configure(scrollregion=self.control_canvas.bbox('all'))
            )
            self.control_canvas.bind('<Configure>', self._on_control_canvas_configure)
            
            # Bind mouse wheel events to control panel
            self.control_canvas.bind('<MouseWheel>', self._on_control_mousewheel)  # Windows
            self.control_canvas.bind('<Button-4>', self._on_control_mousewheel_linux_up)  # Linux scroll up
            self.control_canvas.bind('<Button-5>', self._on_control_mousewheel_linux_down)  # Linux scroll down
            self.control_frame.bind('<MouseWheel>', self._on_control_mousewheel)
            self.control_frame.bind('<Button-4>', self._on_control_mousewheel_linux_up)
            self.control_frame.bind('<Button-5>', self._on_control_mousewheel_linux_down)
        else:
            # Create a vertical layout for landscape images
            # Create frame for the image
            self.image_frame = ttk.Frame(self.main_frame)
            self.image_frame.pack(pady=10)

            # Create frame for controls - for landscape images, set minimum width to image width
            control_width = max(self.scaled_width, control_panel_width)
            self.control_frame = ttk.Frame(self.main_frame, width=control_width)
            self.control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Create label for the image
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack()
        
        # Add status bar
        self._add_status_bar()
    
    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Handle canvas resize events.
        
        Args:
            event: The canvas resize event.
        """
        # Update the width of the scrollable frame when the canvas changes size
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
    
    def _on_control_canvas_configure(self, event: tk.Event) -> None:
        """Handle control panel canvas size changes.
        
        Args:
            event: The control canvas resize event.
        """
        # Update the width of the control panel frame when the canvas changes size
        canvas_width = event.width
        self.control_canvas.itemconfig(self.control_canvas_frame, width=canvas_width)
    
    def _on_control_mousewheel(self, event: tk.Event) -> None:
        """Handle control panel mouse wheel events on Windows.
        
        Args:
            event: The mouse wheel event object.
        """
        if self.is_portrait:
            # Calculate scroll direction (negative for up, positive for down)
            scroll_direction = -1 if event.delta > 0 else 1
            # Scroll the control panel canvas
            self.control_canvas.yview_scroll(scroll_direction, 'units')
    
    def _on_control_mousewheel_linux_up(self, event: tk.Event) -> None:
        """Handle control panel mouse wheel event on Linux (Button-4).
        
        Args:
            event: The mouse wheel event object.
        """
        if self.is_portrait:
            # Scroll up (negative direction)
            self.control_canvas.yview_scroll(-1, 'units')
    
    def _on_control_mousewheel_linux_down(self, event: tk.Event) -> None:
        """Handle control panel mouse wheel event on Linux (Button-5).
        
        Args:
            event: The mouse wheel event object.
        """
        if self.is_portrait:
            # Scroll down (positive direction)
            self.control_canvas.yview_scroll(1, 'units')
    
    def _create_tooltip(self) -> None:
        """Create a tooltip label for displaying messages."""
        self.tooltip = ttk.Label(
            self.root,
            text='',
            background='#ffffe0',
            relief=tk.SOLID,
            borderwidth=1,
            font=('Arial', 10)
        )
        # Tooltip is initially hidden
    
    def show_tooltip(self, message: str) -> None:
        """Show a temporary tooltip message.
        
        Args:
            message: The message to display in the tooltip.
        """
        # Configure the tooltip text
        self.tooltip.configure(text=message)
        
        # Get the current mouse position relative to the root window
        x = self.root.winfo_pointerx() - self.root.winfo_rootx()
        y = self.root.winfo_pointery() - self.root.winfo_rooty()
        
        # Position the tooltip near the mouse
        self.tooltip.place(x=x+15, y=y+10)
        
        # Schedule the tooltip to disappear after 1.5 seconds
        self.root.after(1500, self.hide_tooltip)
        
    def hide_tooltip(self) -> None:
        """Hide the tooltip."""
        self.tooltip.place_forget()
    
    def _add_zoom_controls(self) -> None:
        """Add zoom controls to the interface."""
        self.zoom_frame = ttk.Frame(self.control_frame)
        self.zoom_frame.pack(fill=tk.X, pady=5)

        self.zoom_button_frame = ttk.Frame(self.zoom_frame)
        self.zoom_button_frame.pack(anchor=tk.CENTER, pady=2)

        self.zoom_out_button = ttk.Button(
            self.zoom_button_frame,
            text='Zoom Out (-)',
            command=self.zoom_out
        )
        self.zoom_out_button.pack(side=tk.LEFT)

        self.zoom_in_button = ttk.Button(
            self.zoom_button_frame,
            text='Zoom In (+)',
            command=self.zoom_in
        )
        self.zoom_in_button.pack(side=tk.LEFT, padx=5)

        self.scale_label = ttk.Label(
            self.zoom_frame,
            text=f'Scale: {self.display_scale_factor:.1f}x'
        )
        self.scale_label.pack(anchor=tk.CENTER, pady=1)
    
    def _add_status_bar(self) -> None:
        """Add status bar to the interface."""
        self.status_frame = ttk.Frame(self.control_frame)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        self.status_bar = ttk.Label(
            self.status_frame,
            text='Ready.',
            relief=tk.SUNKEN,
            wraplength=0,  # set to 0, let the text auto-adjust to the control panel width
            anchor=tk.CENTER,
            padding=5,
            font=('Arial', 13)
        )
        self.status_bar.pack(fill=tk.X)
    
    def _bind_common_events(self) -> None:
        """Bind common events to interface elements."""
        self.root.bind('<plus>', lambda e: self.zoom_in())
        self.root.bind('<equal>', lambda e: self.zoom_in())
        self.root.bind('<minus>', lambda e: self.zoom_out())
        self.root.bind('<Escape>', lambda e: self.on_closing())
        self.root.bind('<Return>', self.handle_enter_key)
        
        # Add mouse wheel event bindings
        # Note: Different operating systems use different wheel events
        # Windows uses <MouseWheel>, Linux uses <Button-4> and <Button-5>
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)  # Windows
        self.canvas.bind('<Button-4>', self._on_mousewheel_linux_up)  # Linux scroll up
        self.canvas.bind('<Button-5>', self._on_mousewheel_linux_down)  # Linux scroll down
        
        # For better user experience, also bind to the image label
        self.image_label.bind('<MouseWheel>', self._on_mousewheel)
        self.image_label.bind('<Button-4>', self._on_mousewheel_linux_up)
        self.image_label.bind('<Button-5>', self._on_mousewheel_linux_down)
        
        # To ensure scrolling works throughout the window, also bind to the main frame
        self.scrollable_frame.bind('<MouseWheel>', self._on_mousewheel)
        self.scrollable_frame.bind('<Button-4>', self._on_mousewheel_linux_up)
        self.scrollable_frame.bind('<Button-5>', self._on_mousewheel_linux_down)
    
    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel events on Windows.
        
        On Windows, event.delta is positive for scrolling up and negative for 
        scrolling down. The scroll amount is typically a multiple of 120.
        
        Args:
            event: The mouse wheel event object.
        """
        # Calculate scroll amount (negative for up, positive for down, consistent with canvas.yview direction)
        scroll_direction = -1 if event.delta > 0 else 1
        
        # Scroll the canvas, units means scroll by lines
        self.canvas.yview_scroll(scroll_direction, 'units')

    def _on_mousewheel_linux_up(self, event: tk.Event) -> None:
        """Handle scroll up events on Linux (Button-4).
        
        Args:
            event: The mouse wheel event object.
        """
        # Scroll up (negative direction)
        self.canvas.yview_scroll(-1, 'units')

    def _on_mousewheel_linux_down(self, event: tk.Event) -> None:
        """Handle scroll down events on Linux (Button-5).
        
        Args:
            event: The mouse wheel event object.
        """
        # Scroll down (positive direction)
        self.canvas.yview_scroll(1, 'units')
    
    def center_window(self) -> None:
        """Center the window on the screen."""
        # Update the window to ensure it has the correct size
        self.root.update_idletasks()
        
        # Get window size
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Debug output  
        print(f'center_window - Got window size: width: {width}, height: {height}')
        
        # If winfo_width/height returns 1, this means the window hasn't been fully rendered yet
        # In this case, use the dimensions we set in _set_initial_window_size
        if width <= 1 or height <= 1:
            if hasattr(self, 'requested_width') and hasattr(self, 'requested_height'):
                width = self.requested_width
                height = self.requested_height
                print(f'Using requested window size: width: {width}, height: {height}')
            else:
                # If there is no stored requested size, use the estimated dimensions based on the image
                if self.is_portrait:
                    width = self.scaled_width + 450  # Image width + control panel + padding
                    height = self.scaled_height + 100  # Image height + padding
                else:
                    width = self.scaled_width + 100  # Image width + padding
                    height = self.scaled_height + 300  # Image height + control panel + padding
                
                # Ensure window isn't too large (max 80% of screen)
                max_width = int(self.screen_width * 0.8)
                max_height = int(self.screen_height * 0.8)
                
                width = min(width, max_width)
                height = min(height, max_height)
                
                print(f'Using estimated window size: width: {width}, height: {height}')
        
        # If window is too tall for the screen, adjust height to 90% of screen
        if height > self.screen_height * 0.9:
            height = int(self.screen_height * 0.9)
            self.root.geometry(f'{width}x{height}')
        
        # If window is too wide for the screen, adjust width to 90% of screen   
        if width > self.screen_width * 0.9:
            width = int(self.screen_width * 0.9)
            self.root.geometry(f'{width}x{height}')
            
        # Calculate position
        x = (self.screen_width - width) // 2
        y = (self.screen_height - height) // 2
        
        # Set the position
        self.root.geometry(f'+{x}+{y}')
        print(f'Set window geometry: {width}x{height}+{x}+{y}')
    
    def update_image_display(self, image: Optional[Image.Image] = None) -> None:
        """Update the image display.
        
        Args:
            image: The image to display. If None, displays the original image.
        """
        # Use the provided image or the original
        display_image = image if image is not None else self.original_image.copy()
        
        # Resize the image according to display scale factor
        scaled_image = display_image.resize(
            (int(self.width * self.display_scale_factor),
             int(self.height * self.display_scale_factor)),
            Image.Resampling.LANCZOS
        )
        
        # Add debug output
        print(f'Displaying image: Width: {self.width}, Height: {self.height}, Scale: {self.display_scale_factor}')
        print(f'Scaled size: {int(self.width * self.display_scale_factor)}x{int(self.height * self.display_scale_factor)}')
        
        # Convert to PhotoImage and update the label
        self.photo_image = ImageTk.PhotoImage(scaled_image)
        self.image_label.configure(image=self.photo_image)
        
        # Update scale label if it exists
        if hasattr(self, 'scale_label'):
            self.scale_label.configure(text=f'Scale: {self.display_scale_factor:.1f}x')
    
    def zoom_in(self, max_scale: float = 0.8) -> None:
        """Increase the zoom level.

        Args:
            max_scale: Maximum zoom level. Defaults to 0.8.
        """
        if self.display_scale_factor < max_scale:  # Don't allow too large
            self.display_scale_factor += 0.1
            self.update_image_display()
        else:
            self.show_tooltip('Maximum zoom level reached')
    
    def zoom_out(self, min_scale: float = 0.5) -> None:
        """Decrease the zoom level.

        Args:
            min_scale: Minimum zoom level. Defaults to 0.5.
        """
        if self.display_scale_factor > min_scale:  # Don't allow too small
            self.display_scale_factor -= 0.1
            self.update_image_display()
        else:
            self.show_tooltip('Minimum zoom level reached')
    
    def on_closing(self) -> None:
        """Handle window closing event."""
        # Ask for confirmation before closing
        if messagebox.askyesno('Confirm Close', 'Are you sure you want to close?'):
            self.root.destroy()
            # Call the callback function if provided
            if self.on_complete_callback:
                self.on_complete_callback()
    
    def run(self) -> None:
        """Run the main application loop."""
        self.root.mainloop()
    
    def _set_initial_window_size(self) -> None:
        """Set an appropriate initial window size based on image and controls."""
        # Calculate the scaled dimensions of the image
        scaled_width = int(self.width * self.scale_factor)
        scaled_height = int(self.height * self.scale_factor)
        
        # Add padding and space for controls
        if self.is_portrait:
            # For portrait images, add width for the control panel
            window_width = scaled_width + 450  # Image width + control panel + padding
            # Ensure window height can accommodate at least the image height or minimum control panel height (whichever is larger) plus padding
            min_content_height = max(scaled_height, 500)  # Minimum control panel height is 500
            window_height = min_content_height + 100  # Content height + padding
        else:
            # For landscape images, add height for controls below
            window_width = scaled_width + 100  # Image width + padding
            window_height = scaled_height + 300  # Image height + control panel + padding
        
        # Ensure window isn't too large for the screen (80% of screen max)
        max_width = int(self.screen_width * 0.8)
        max_height = int(self.screen_height * 0.8)
        
        window_width = min(window_width, max_width)
        window_height = min(window_height, max_height)
        
        # Store requested window size for use in center_window
        self.requested_width = window_width
        self.requested_height = window_height
        
        # Set window size
        self.root.geometry(f'{window_width}x{window_height}')
        print(f'Set initial window size: {window_width}x{window_height}')
    
    def update_status(self, message: str) -> None:
        """Update the status bar message.
        
        Args:
            message: The message to display in the status bar.
        """
        self.status_bar.configure(text=message)
        
    def draw_on_image(self, draw_function: Callable[[Image.Image], Image.Image], *args: Any, **kwargs: Any) -> None:
        """Draw on the image using a provided drawing function.
        
        Args:
            draw_function: Function that takes an Image and draws on it.
            *args: Additional arguments to pass to the draw function.
            **kwargs: Additional keyword arguments to pass to the draw function.
        """
        # Create a copy of the original image
        image_copy = self.original_image.copy()
        
        # Call the drawing function
        result_image = draw_function(image_copy, *args, **kwargs)
        
        # Update the display with the drawn image
        self.update_image_display(result_image)
        
    def handle_enter_key(self, event: Optional[tk.Event] = None) -> None:
        """Default handler for Enter key press.
        
        This method should be overridden by subclasses to provide specific behavior.
        
        Args:
            event: The key event.
        """
        pass 
    
    def _add_description_input(self, frame_title: str = 'Description') -> None:
        """Add a general description input area.
        
        Args:
            frame_title: Title of the input frame. Defaults to "Description".
        """
        self.description_frame = ttk.LabelFrame(self.control_frame, text=frame_title)
        self.description_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.description_input = scrolledtext.ScrolledText(
            self.description_frame,
            height=5,
            wrap=tk.WORD,
            font=('Arial', 12)
        )
        self.description_input.pack(fill=tk.X, pady=5, padx=5)
        
        self.save_button = ttk.Button(
            self.description_frame,
            text='Save Description',
            command=self._handle_save_description
        )
        self.save_button.pack(side=tk.RIGHT, pady=5, padx=5)
        
        # Set focus to the input box by default
        self.description_input.focus_set()
    
    def _handle_save_description(self) -> None:
        """Handle save description button click.
        
        This is a basic implementation, subclasses should override this method to provide specific behavior.
        """
        description = self.description_input.get('1.0', 'end-1c').strip()
        if description:
            self.update_status(f'Description saved: "{description[:50]}{"..." if len(description) > 50 else ""}"')
    
    def _add_progress_indicator(self, current: int, total: int) -> None:
        """Add a progress indicator.
        
        Args:
            current: Current position
            total: Total count
        """
        self.progress_label = ttk.Label(
            self.control_frame,
            text=f'Progress: {current} / {total}',
            font=('Arial', 14, 'bold'),
            wraplength=0  # Set to 0 to auto-adjust to control panel width
        )
        self.progress_label.pack(anchor=tk.W if not self.is_portrait else tk.CENTER, pady=(0, 5), fill=tk.X)
    
    def update_progress(self, current: int, total: int) -> None:
        """Update the progress indicator.
        
        Args:
            current: Current position
            total: Total count
        """
        if hasattr(self, 'progress_label'):
            self.progress_label.configure(text=f'Progress: {current} / {total}')
            
    def _add_text_display(self, height: int = 5, readonly: bool = True) -> None:
        """Add a text display area.
        
        Args:
            height: Height of the text area in lines. Defaults to 5.
            readonly: Whether the text area should be read-only. Defaults to True.
        """
        self.text_display_frame = ttk.LabelFrame(self.control_frame)
        self.text_display_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.text_display = scrolledtext.ScrolledText(
            self.text_display_frame,
            height=height,
            wrap=tk.WORD,
            font=('Arial', 12)
        )
        self.text_display.pack(fill=tk.X, pady=5, padx=5)
        
        if readonly:
            self.text_display.configure(state='disabled')
            
    def update_text_display(self, text: str) -> None:
        """Update the text in the text display area.
        
        Args:
            text: The text to display.
        """
        if hasattr(self, 'text_display'):
            self.text_display.configure(state='normal')
            self.text_display.delete('1.0', tk.END)
            self.text_display.insert('1.0', text)
            self.text_display.configure(state='disabled')