import salabim as sim
import logging
import os
import math
import subprocess
import tempfile
import msgpack  # Faster caching alternative to pickle
import hashlib  # Added import
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QImage, QPixmap
import xml.etree.ElementTree as ET

# Optional DXF support
try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    logging.warning("ezdxf library not found. DXF support will be limited.")

# Optional PDF support
try:
    import fitz  # PyMuPDF for PDF handling
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF library not found. PDF support will be limited.")

# Optional CAD conversion support
try:
    from oda_file_converter import convert_cad_to_dxf
    ODA_AVAILABLE = True
except ImportError:
    ODA_AVAILABLE = False
    logging.warning("ODA File Converter not found. CAD conversion will be limited.")

logger = logging.getLogger(__name__)

class CADBackground:
    """
    Handles loading and displaying CAD backgrounds for the simulation with optimized performance.
    Supports DXF, SVG, CAD/DWG (via conversion), and PDF files, with caching and layer management.
    """
    def __init__(self, env, layer_manager, config=None, parent_widget=None):
        self.env = env
        self.layer_manager = layer_manager
        self.config = config or {}
        self.cad_elements = {}  # Elements organized by layer
        self.cad_file_path = self.config.get("cad_file_path", None)
        self.background_image = self.config.get("background_image", None)
        self.background_type = self.config.get("background_type", "image")  # Default to image
        self.scale = self.config.get("cad_scale", 1.0)
        self.x_offset = self.config.get("cad_x_offset", 0)
        self.y_offset = self.config.get("cad_y_offset", 0)
        self.parent_widget = parent_widget
        self.layers = {}  # Store layer info
        self.visible_layers = self.config.get("cad_visible_layers", [])  # Empty means all visible
        self.simplify_options = self.config.get("simplify_options", {})  # User-controlled simplification

        # PDF specific parameters
        self.pdf_real_width = self.config.get("pdf_real_width", 100.0)  # Real-world width in meters
        self.pdf_real_height = self.config.get("pdf_real_height", 100.0)  # Real-world height in meters
        self.temp_image_path = None  # Path to temporary image file for PDF rendering

        # Grid defaults
        self.grid_size = self.config.get("grid_size", 100)
        self.grid_width = self.config.get("grid_width", 1000)
        self.grid_height = self.config.get("grid_height", 1000)

        # Caching setup
        self.cache_dir = os.path.join(tempfile.gettempdir(), "steel_plant_sim_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_enabled = self.config.get("cad_cache_enabled", True)
        self.cached_files = {}

        # Initialize background
        self.create_background()

    def create_background(self):
        """Create background based on config with fallback."""
        try:
            # First check background_type to determine which type of background to use
            if self.background_type == "image" and self.background_image and os.path.exists(self.background_image):
                logger.info(f"Using image background from {self.background_image}")
                self.load_background_image(self.background_image)
            elif self.background_type == "pdf" and self.cad_file_path and os.path.exists(self.cad_file_path) and self.cad_file_path.lower().endswith('.pdf'):
                logger.info(f"Using PDF background from {self.cad_file_path}")
                self.load_pdf_file()
            elif self.background_type == "cad" and self.cad_file_path and os.path.exists(self.cad_file_path):
                logger.info(f"Using CAD background from {self.cad_file_path}")
                self.load_cad_file()
            else:
                # Fallback to available files if background_type doesn't match available files
                if self.background_image and os.path.exists(self.background_image):
                    logger.info(f"Falling back to image background from {self.background_image}")
                    self.load_background_image(self.background_image)
                elif self.cad_file_path and os.path.exists(self.cad_file_path):
                    if self.cad_file_path.lower().endswith('.pdf'):
                        logger.info(f"Falling back to PDF background from {self.cad_file_path}")
                        self.load_pdf_file()
                    else:
                        logger.info(f"Falling back to CAD background from {self.cad_file_path}")
                        self.load_cad_file()
                else:
                    self.create_grid()
                    logger.info("No background files available. Using grid fallback.")
        except Exception as e:
            logger.error(f"Error creating background: {e}")
            self.create_grid()  # Fallback to grid if loading fails
    
    def load_background_image(self, image_path):
        """Load an image file as background."""
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return False
                
            # Load the image file
            image = QImage(image_path)
            if image.isNull():
                logger.error(f"Failed to load image: {image_path}")
                return False
                
            # Get image dimensions
            width = image.width()
            height = image.height()
            logger.info(f"Loaded image with dimensions {width}x{height}")
            
            # Create a background using salabim's Animate
            # Remove existing background elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            
            # Set the image as background with proper positioning and scale
            bg = sim.Animate(image=image_path, x0=0, y0=0, 
                           width=width, height=height, 
                           layer=0, screen_coordinates=False)
                           
            # Register with the layer manager
            self.layer_manager.add_layer("Background", visible=True)
            self.cad_elements["Background"] = [bg]
            
            # Update the configuration
            self.config["background_image"] = image_path
            self.config["background_type"] = "image"
            
            return True
        except Exception as e:
            logger.error(f"Error loading background image: {e}")
            return False

    def load_pdf_file(self):
        """Load PDF file as background with proper scaling."""
        if not PYMUPDF_AVAILABLE:
            logger.error("PyMuPDF not available. Cannot load PDF.")
            self.create_grid()
            return

        try:
            logger.info(f"Loading PDF file: {self.cad_file_path}")
            
            # Clear existing elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}

            # Calculate scale based on real-world dimensions
            if self.config.get("auto_scale_cad", True):
                self.calculate_pdf_scale()
                logger.info(f"Auto-detected PDF scale: {self.scale}")

            # Load the PDF using PyMuPDF
            doc = fitz.open(self.cad_file_path)
            if doc.page_count == 0:
                logger.error("PDF file contains no pages")
                self.create_grid()
                return

            # Get the first page and render it at a reasonable resolution
            page = doc.load_page(0)
            
            # Check if rotation is needed
            page_rect = page.rect
            rotation = 0
            if page_rect.width < page_rect.height:
                rotation = 90  # Apply 90-degree rotation for portrait PDFs
                logger.info("Portrait PDF detected, rotating...")
                
            resolution = 2.0  # Increase for higher quality
            matrix = fitz.Matrix(resolution, resolution).prerotate(rotation)
            pix = page.get_pixmap(matrix=matrix)
            
            # Save to a temporary file
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                try:
                    os.remove(self.temp_image_path)
                except:
                    pass
                    
            self.temp_image_path = os.path.join(tempfile.gettempdir(), f"pdf_background_{hash(self.cad_file_path)}.png")
            pix.save(self.temp_image_path)
            
            # Calculate dimensions
            img_width = pix.width
            img_height = pix.height
            
            # Calculate the aspect ratio of the PDF
            pdf_aspect = img_width / img_height
            
            # Calculate the target dimensions based on real-world dimensions and scale
            target_width = self.pdf_real_width * self.scale
            target_height = self.pdf_real_height * self.scale
            
            # Center the image on the grid
            x_offset = (self.grid_width - target_width) / 2
            y_offset = (self.grid_height - target_height) / 2
            
            # Create an Animate object for the PDF
            bg = sim.Animate(image=self.temp_image_path, 
                           x0=x_offset, y0=y_offset,
                           width=target_width, height=target_height,
                           screen_coordinates=False)
            
            # Add to the layer manager
            self.layer_manager.add_layer("PDF Background", visible=True)
            self.cad_elements["PDF Background"] = [bg]
            
            # Create grid overlay
            if self.config.get("show_grid_overlay", True):
                self.create_grid_overlay(target_width, target_height, x_offset, y_offset)
            
            # Update configuration
            self.config["background_type"] = "pdf"
            logger.info(f"PDF background loaded with dimensions {target_width}x{target_height}")
            doc.close()
            return True
        except Exception as e:
            logger.error(f"Error loading PDF background: {e}")
            self.create_grid()
            return False
    
    def calculate_pdf_scale(self):
        """Calculate scale factor for PDF based on real-world dimensions."""
        try:
            if PYMUPDF_AVAILABLE and self.cad_file_path and os.path.exists(self.cad_file_path):
                doc = fitz.open(self.cad_file_path)
                if doc.page_count > 0:
                    page = doc.load_page(0)
                    page_width = page.rect.width
                    page_height = page.rect.height
                    
                    # Calculate scale based on grid dimensions and real-world dimensions
                    grid_width = self.grid_width
                    grid_height = self.grid_height
                    
                    # Use the largest dimension to fit in the grid while maintaining aspect ratio
                    width_scale = grid_width * 0.9 / self.pdf_real_width
                    height_scale = grid_height * 0.9 / self.pdf_real_height
                    
                    # Use the smaller scale to ensure both dimensions fit
                    self.scale = min(width_scale, height_scale)
                    
                    doc.close()
                    logger.info(f"Auto-calculated PDF scale: {self.scale}")
        except Exception as e:
            logger.error(f"Error calculating PDF scale: {e}")

    def create_grid_overlay(self, width, height, x_offset, y_offset):
        """Create a grid overlay on top of the PDF or image."""
        try:
            grid_layer = []
            grid_size = self.config.get("grid_size", 100)
            
            # Create grid lines
            for x in range(0, int(width) + grid_size, grid_size):
                line = sim.AnimateLine(x0=x_offset + x, y0=y_offset, 
                                     x1=x_offset + x, y1=y_offset + height,
                                     linecolor="lightgray", linewidth=1, 
                                     screen_coordinates=False)
                grid_layer.append(line)
                
            for y in range(0, int(height) + grid_size, grid_size):
                line = sim.AnimateLine(x0=x_offset, y0=y_offset + y, 
                                     x1=x_offset + width, y1=y_offset + y,
                                     linecolor="lightgray", linewidth=1, 
                                     screen_coordinates=False)
                grid_layer.append(line)
                
            # Add coordinate indicators
            for x in range(0, int(width) + grid_size, grid_size):
                text = sim.AnimateText(text=str(x // grid_size), 
                                     x0=x_offset + x, y0=y_offset - 20,
                                     textcolor="gray", fontsize=10,
                                     screen_coordinates=False)
                grid_layer.append(text)
                
            for y in range(0, int(height) + grid_size, grid_size):
                text = sim.AnimateText(text=str(y // grid_size), 
                                     x0=x_offset - 20, y0=y_offset + y,
                                     textcolor="gray", fontsize=10,
                                     screen_coordinates=False)
                grid_layer.append(text)
                
            # Add to layer manager
            self.layer_manager.add_layer("Grid Overlay", visible=self.config.get("show_grid_overlay", True))
            self.cad_elements["Grid Overlay"] = grid_layer
            
        except Exception as e:
            logger.error(f"Error creating grid overlay: {e}")

    def load_cad_file(self):
        """Load and parse a CAD file."""
        if not self.cad_file_path or not os.path.exists(self.cad_file_path):
            logger.error("No CAD file provided or file does not exist")
            self.create_grid()
            return

        file_ext = os.path.splitext(self.cad_file_path)[1].lower()
        if file_ext == '.dxf' and EZDXF_AVAILABLE:
            self.load_dxf_file()
        elif file_ext == '.svg':
            self.load_svg_file()
        else:
            # Try to convert to DXF if not directly supported
            if ODA_AVAILABLE:
                dxf_path = self.convert_to_dxf(self.cad_file_path)
                if dxf_path and EZDXF_AVAILABLE:
                    self.cad_file_path = dxf_path
                    self.load_dxf_file()
                else:
                    logger.error(f"Unsupported CAD format: {file_ext}")
                    self.create_grid()
            else:
                logger.error(f"Unsupported CAD format: {file_ext}")
                self.create_grid()
                
        # Update configuration
        self.config["background_type"] = "cad"

    def load_dxf_file(self):
        """Load a DXF file and create entities."""
        try:
            # Check if we have a cached version
            cache_file = None
            if self.cache_enabled:
                cache_file = self.get_cache_path(self.cad_file_path)
                if os.path.exists(cache_file):
                    self.load_from_cache(cache_file)
                    return
                    
            # Clear existing elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}
            
            # Parse the DXF file
            logger.info(f"Loading DXF file: {self.cad_file_path}")
            doc = ezdxf.readfile(self.cad_file_path)
            modelspace = doc.modelspace()
            
            # Extract layers
            layers = {}
            for layer in doc.layers:
                layers[layer.dxf.name] = {
                    'name': layer.dxf.name,
                    'color': layer.get_color(),
                    'linetype': layer.dxf.linetype,
                    'visible': not layer.is_off(),
                    'locked': layer.is_locked()
                }
            self.layers = layers
            
            # Register layers with layer manager
            for layer_name, layer_props in layers.items():
                visible = layer_props['visible']
                if self.visible_layers:  # If specific layers are set to be visible
                    visible = layer_name in self.visible_layers
                self.layer_manager.add_layer(layer_name, visible=visible)
                
            # Filter visible layers
            visible_layers = set(layer_name for layer_name, props in layers.items() 
                              if props['visible'] and (not self.visible_layers or layer_name in self.visible_layers))
            
            # Process entities in batches to prevent UI freezing
            batch_size = 1000  # Adjust based on complexity
            entities = list(modelspace)
            
            # Get bounds for scaling
            auto_scale = self.config.get("auto_scale_cad", True)
            if auto_scale:
                scale_factor = self.calculate_dxf_scale(entities)
                if scale_factor:
                    self.scale = scale_factor
                    
            # Calculate center offset
            min_x, min_y, max_x, max_y = self.get_bounds(entities)
            center_x = (max_x + min_x) / 2
            center_y = (max_y + min_y) / 2
            grid_center_x = self.grid_width / 2
            grid_center_y = self.grid_height / 2
            x_offset = grid_center_x - center_x * self.scale
            y_offset = grid_center_y - center_y * self.scale
            
            if "cad_x_offset" in self.config and "cad_y_offset" in self.config:
                x_offset = self.config["cad_x_offset"]
                y_offset = self.config["cad_y_offset"]
            else:
                self.config["cad_x_offset"] = x_offset
                self.config["cad_y_offset"] = y_offset
                
            # Process entities in batches
            for i in range(0, len(entities), batch_size):
                batch = entities[i:i+batch_size]
                if i == 0:
                    logger.info(f"Processing DXF entities: {len(entities)} total in batches of {batch_size}")
                
                self.process_dxf_batch(batch, visible_layers, x_offset, y_offset)
            
            # Save to cache
            if self.cache_enabled and cache_file:
                self.save_to_cache(cache_file)
                
            logger.info(f"DXF file loaded with {len(entities)} entities")
            return True
        except Exception as e:
            logger.error(f"Error loading DXF file: {e}")
            self.create_grid()
            return False

    def process_dxf_batch(self, entities, visible_layers, x_offset, y_offset):
        """Process a batch of DXF entities."""
        for entity in entities:
            try:
                layer_name = entity.dxf.layer
                if layer_name not in visible_layers:
                    continue
                
                # Skip hidden entities
                if hasattr(entity.dxf, 'invisible') and entity.dxf.invisible:
                    continue
                    
                # Simplification options
                min_line_length = self.simplify_options.get("min_line_length", 0)
                skip_text = self.simplify_options.get("skip_text", False)
                skip_points = self.simplify_options.get("skip_points", True)
                    
                if layer_name not in self.cad_elements:
                    self.cad_elements[layer_name] = []
                    
                # Get entity color
                color = 'white'  # Default
                if hasattr(entity.dxf, 'color'):
                    color_idx = entity.dxf.color
                    # Convert DXF color index to RGB
                    # This is a simplified approach - DXF colors are complex
                    if color_idx == 1:
                        color = 'red'
                    elif color_idx == 2:
                        color = 'yellow'
                    elif color_idx == 3:
                        color = 'green'
                    elif color_idx == 4:
                        color = 'cyan'
                    elif color_idx == 5:
                        color = 'blue'
                    elif color_idx == 6:
                        color = 'magenta'
                    elif color_idx == 7:
                        color = 'white'
                
                # Handle different entity types
                if entity.dxftype() == 'LINE':
                    # Skip very short lines if simplification is enabled
                    if min_line_length > 0:
                        length = ((entity.dxf.end.x - entity.dxf.start.x)**2 + 
                                  (entity.dxf.end.y - entity.dxf.start.y)**2)**0.5
                        if length < min_line_length:
                            continue
                    
                    line = sim.AnimateLine(
                        x0=entity.dxf.start.x * self.scale + x_offset,
                        y0=entity.dxf.start.y * self.scale + y_offset,
                        x1=entity.dxf.end.x * self.scale + x_offset,
                        y1=entity.dxf.end.y * self.scale + y_offset,
                        linecolor=color,
                        linewidth=1,
                        layer=layer_name,
                        screen_coordinates=False
                    )
                    self.cad_elements[layer_name].append(line)
                    
                elif entity.dxftype() == 'CIRCLE':
                    circle = sim.AnimateCircle(
                        x0=entity.dxf.center.x * self.scale + x_offset,
                        y0=entity.dxf.center.y * self.scale + y_offset,
                        radius=entity.dxf.radius * self.scale,
                        linecolor=color,
                        linewidth=1,
                        layer=layer_name,
                        screen_coordinates=False
                    )
                    self.cad_elements[layer_name].append(circle)
                    
                elif entity.dxftype() == 'ARC':
                    # Arcs are complex to represent directly in salabim
                    # For now, we'll convert to line segments
                    segments = 20  # Number of line segments to use for arc
                    start_angle = entity.dxf.start_angle
                    end_angle = entity.dxf.end_angle
                    if end_angle < start_angle:
                        end_angle += 360
                    angle_step = (end_angle - start_angle) / segments
                    
                    points = []
                    for i in range(segments + 1):
                        angle = math.radians(start_angle + i * angle_step)
                        x = entity.dxf.center.x + entity.dxf.radius * math.cos(angle)
                        y = entity.dxf.center.y + entity.dxf.radius * math.sin(angle)
                        points.append((x, y))
                    
                    for i in range(segments):
                        line = sim.AnimateLine(
                            x0=points[i][0] * self.scale + x_offset,
                            y0=points[i][1] * self.scale + y_offset,
                            x1=points[i+1][0] * self.scale + x_offset,
                            y1=points[i+1][1] * self.scale + y_offset,
                            linecolor=color,
                            linewidth=1,
                            layer=layer_name,
                            screen_coordinates=False
                        )
                        self.cad_elements[layer_name].append(line)
                        
                elif entity.dxftype() == 'TEXT' and not skip_text:
                    text = sim.AnimateText(
                        text=entity.dxf.text,
                        x0=entity.dxf.insert.x * self.scale + x_offset,
                        y0=entity.dxf.insert.y * self.scale + y_offset,
                        textcolor=color,
                        fontsize=entity.dxf.height * self.scale if entity.dxf.height else 12,
                        layer=layer_name,
                        screen_coordinates=False
                    )
                    self.cad_elements[layer_name].append(text)
                    
                elif entity.dxftype() == 'POLYLINE' or entity.dxftype() == 'LWPOLYLINE':
                    # Convert to line segments
                    points = list(entity.vertices()) if entity.dxftype() == 'POLYLINE' else list(entity.points())
                    if len(points) < 2:
                        continue
                        
                    for i in range(len(points) - 1):
                        if entity.dxftype() == 'POLYLINE':
                            p1, p2 = points[i].dxf.location, points[i+1].dxf.location
                            x1, y1, z1 = p1
                            x2, y2, z2 = p2
                        else:
                            x1, y1 = points[i]
                            x2, y2 = points[i+1]
                            
                        # Skip very short segments if simplification is enabled
                        if min_line_length > 0:
                            length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                            if length < min_line_length:
                                continue
                        
                        line = sim.AnimateLine(
                            x0=x1 * self.scale + x_offset,
                            y0=y1 * self.scale + y_offset,
                            x1=x2 * self.scale + x_offset,
                            y1=y2 * self.scale + y_offset,
                            linecolor=color,
                            linewidth=1,
                            layer=layer_name,
                            screen_coordinates=False
                        )
                        self.cad_elements[layer_name].append(line)
                    
                    # Close the polyline if it's closed
                    if hasattr(entity.dxf, 'closed') and entity.dxf.closed:
                        if entity.dxftype() == 'POLYLINE':
                            p1, p2 = points[-1].dxf.location, points[0].dxf.location
                            x1, y1, z1 = p1
                            x2, y2, z2 = p2
                        else:
                            x1, y1 = points[-1]
                            x2, y2 = points[0]
                            
                        line = sim.AnimateLine(
                            x0=x1 * self.scale + x_offset,
                            y0=y1 * self.scale + y_offset,
                            x1=x2 * self.scale + x_offset,
                            y1=y2 * self.scale + y_offset,
                            linecolor=color,
                            linewidth=1,
                            layer=layer_name,
                            screen_coordinates=False
                        )
                        self.cad_elements[layer_name].append(line)
                
                elif entity.dxftype() == 'POINT' and not skip_points:
                    point = sim.AnimateRectangle(
                        x0=entity.dxf.location.x * self.scale + x_offset - 1,
                        y0=entity.dxf.location.y * self.scale + y_offset - 1,
                        width=2,
                        height=2,
                        fillcolor=color,
                        linecolor=color,
                        layer=layer_name,
                        screen_coordinates=False
                    )
                    self.cad_elements[layer_name].append(point)
                    
            except Exception as e:
                logger.warning(f"Error processing DXF entity: {e}")

    def load_svg_file(self):
        """Load an SVG file."""
        try:
            tree = ET.parse(self.cad_file_path)
            root = tree.getroot()
            
            # Clear existing elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            
            # Default layer
            self.layer_manager.add_layer("SVG", visible=True)
            self.cad_elements["SVG"] = []
            
            # Get SVG dimensions
            width = float(root.get('width', '100').replace('px', ''))
            height = float(root.get('height', '100').replace('px', ''))
            
            # Calculate scale factor to fit in grid
            if self.config.get("auto_scale_cad", True):
                scale_x = self.grid_width / width
                scale_y = self.grid_height / height
                self.scale = min(scale_x, scale_y) * 0.9  # 90% of available space
            
            # This would be a much more extensive parser for SVG
            # For now, just create a placeholder
            logger.warning("SVG parsing is limited. Consider converting to DXF for better results.")
            
            # Use the SVG file as a background image if possible
            # This is a fallback method
            # Convert SVG to PNG using a library or external tool if needed
            
            # Create a placeholder frame to show boundaries
            frame = sim.AnimateRectangle(
                x0=0, y0=0,
                width=width * self.scale,
                height=height * self.scale,
                linecolor='white',
                linewidth=1,
                fillcolor=None,
                screen_coordinates=False
            )
            self.cad_elements["SVG"].append(frame)
            
            # Add a label
            text = sim.AnimateText(
                text=f"SVG: {os.path.basename(self.cad_file_path)}",
                x0=width * self.scale / 2,
                y0=height * self.scale / 2,
                textcolor='white',
                fontsize=12,
                screen_coordinates=False
            )
            self.cad_elements["SVG"].append(text)
            
            return True
        except Exception as e:
            logger.error(f"Error loading SVG file: {e}")
            self.create_grid()
            return False

    def convert_to_dxf(self, file_path):
        """Convert a CAD file to DXF format."""
        try:
            if ODA_AVAILABLE:
                dxf_path = file_path.rsplit('.', 1)[0] + '.dxf'
                result = convert_cad_to_dxf(file_path, dxf_path)
                if result and os.path.exists(dxf_path):
                    logger.info(f"Converted {file_path} to {dxf_path}")
                    return dxf_path
            return None
        except Exception as e:
            logger.error(f"Error converting CAD file to DXF: {e}")
            return None

    def create_grid(self):
        """Create a simple grid background."""
        try:
            # Clear existing elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            
            # Create a grid layer
            self.layer_manager.add_layer("Grid", visible=True)
            self.cad_elements["Grid"] = []
            
            # Grid properties
            grid_size = self.grid_size
            width = self.grid_width
            height = self.grid_height
            
            # Create horizontal and vertical lines
            for x in range(0, width + grid_size, grid_size):
                line = sim.AnimateLine(x0=x, y0=0, x1=x, y1=height,
                                     linecolor='gray', linewidth=1,
                                     screen_coordinates=False)
                self.cad_elements["Grid"].append(line)
                
            for y in range(0, height + grid_size, grid_size):
                line = sim.AnimateLine(x0=0, y0=y, x1=width, y1=y,
                                     linecolor='gray', linewidth=1,
                                     screen_coordinates=False)
                self.cad_elements["Grid"].append(line)
                
            # Create coordinate labels at regular intervals
            label_interval = 5 * grid_size
            for x in range(0, width + label_interval, label_interval):
                text = sim.AnimateText(text=str(x), x0=x, y0=-20,
                                     textcolor='white', fontsize=10,
                                     screen_coordinates=False)
                self.cad_elements["Grid"].append(text)
                
            for y in range(0, height + label_interval, label_interval):
                text = sim.AnimateText(text=str(y), x0=-20, y0=y,
                                     textcolor='white', fontsize=10,
                                     screen_coordinates=False)
                self.cad_elements["Grid"].append(text)
                
            # Update configuration
            self.config["background_type"] = "grid"
            logger.info(f"Created grid background {width}x{height} with grid size {grid_size}")
            return True
        except Exception as e:
            logger.error(f"Error creating grid: {e}")
            return False

    def get_bounds(self, entities):
        """Calculate bounds of all entities."""
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for entity in entities:
            try:
                if entity.dxftype() == 'LINE':
                    min_x = min(min_x, entity.dxf.start.x, entity.dxf.end.x)
                    min_y = min(min_y, entity.dxf.start.y, entity.dxf.end.y)
                    max_x = max(max_x, entity.dxf.start.x, entity.dxf.end.x)
                    max_y = max(max_y, entity.dxf.start.y, entity.dxf.end.y)
                elif entity.dxftype() == 'CIRCLE':
                    min_x = min(min_x, entity.dxf.center.x - entity.dxf.radius)
                    min_y = min(min_y, entity.dxf.center.y - entity.dxf.radius)
                    max_x = max(max_x, entity.dxf.center.x + entity.dxf.radius)
                    max_y = max(max_y, entity.dxf.center.y + entity.dxf.radius)
                elif entity.dxftype() == 'ARC':
                    # Simplified bounds for arc
                    min_x = min(min_x, entity.dxf.center.x - entity.dxf.radius)
                    min_y = min(min_y, entity.dxf.center.y - entity.dxf.radius)
                    max_x = max(max_x, entity.dxf.center.x + entity.dxf.radius)
                    max_y = max(max_y, entity.dxf.center.y + entity.dxf.radius)
                elif entity.dxftype() == 'TEXT':
                    min_x = min(min_x, entity.dxf.insert.x)
                    min_y = min(min_y, entity.dxf.insert.y)
                    max_x = max(max_x, entity.dxf.insert.x)
                    max_y = max(max_y, entity.dxf.insert.y)
                elif entity.dxftype() == 'POLYLINE':
                    for vertex in entity.vertices():
                        x, y, z = vertex.dxf.location
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
                elif entity.dxftype() == 'LWPOLYLINE':
                    for point in entity.points():
                        x, y = point
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
                elif entity.dxftype() == 'POINT':
                    min_x = min(min_x, entity.dxf.location.x)
                    min_y = min(min_y, entity.dxf.location.y)
                    max_x = max(max_x, entity.dxf.location.x)
                    max_y = max(max_y, entity.dxf.location.y)
            except Exception as e:
                logger.warning(f"Error calculating bounds for entity: {e}")
                
        # Handle case where no entities were processed
        if min_x == float('inf'):
            min_x = min_y = 0
            max_x = max_y = 1000
            
        return min_x, min_y, max_x, max_y

    def calculate_dxf_scale(self, entities):
        """Calculate optimal scale factor for DXF entities."""
        min_x, min_y, max_x, max_y = self.get_bounds(entities)
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width <= 0 or height <= 0:
            return 1.0
            
        # Calculate scale to fit in grid (90% of available space)
        scale_x = (self.grid_width * 0.9) / width
        scale_y = (self.grid_height * 0.9) / height
        
        return min(scale_x, scale_y)

    def get_cache_path(self, file_path):
        """Generate a cache path for a file."""
        # Create a unique hash of the file
        file_stat = os.stat(file_path)
        file_hash = hashlib.md5(f"{file_path}_{file_stat.st_size}_{file_stat.st_mtime}".encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{file_hash}.cache")

    def save_to_cache(self, cache_path):
        """Save parsed CAD elements to cache."""
        # We can't directly cache the animate objects, but we can cache their parameters
        try:
            cache_data = {
                'file_path': self.cad_file_path,
                'scale': self.scale,
                'x_offset': self.x_offset,
                'y_offset': self.y_offset,
                'layers': self.layers,
                # We would need a serializable representation of the elements
                # This is a complex task beyond the scope of this implementation
            }
            with open(cache_path, 'wb') as f:
                msgpack.dump(cache_data, f)
            logger.info(f"CAD data cached to {cache_path}")
        except Exception as e:
            logger.error(f"Error saving CAD cache: {e}")

    def load_from_cache(self, cache_path):
        """Load parsed CAD elements from cache."""
        try:
            with open(cache_path, 'rb') as f:
                cache_data = msgpack.load(f)
            logger.info(f"Loaded CAD data from cache: {cache_path}")
            
            # We would reconstruct the elements here
            # For now, just log that we found a cache but still load the original file
            logger.info("Cache loading is limited. Falling back to normal loading.")
            
            # Reset to trigger normal loading
            self.load_dxf_file()
        except Exception as e:
            logger.error(f"Error loading CAD cache: {e}")
            self.load_dxf_file()  # Fallback to normal loading