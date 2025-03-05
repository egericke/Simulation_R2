import salabim as sim
import logging
from abc import ABC, abstractmethod
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel, QGroupBox, QScrollArea
from PyQt5.QtCore import pyqtSignal

logger = logging.getLogger(__name__)

# New formal interface definition
class ILayerManager(ABC):
    """Interface defining the required methods for layer management."""
    
    @abstractmethod
    def add_cad_layer(self, layer_name, visible=True):
        """Register a CAD layer for visualization control."""
        pass
    
    @abstractmethod
    def get_layer(self, name):
        """Get a layer by name, creating it if it doesn't exist."""
        pass
    
    @abstractmethod
    def set_layer_visibility(self, name, visible):
        """Set the visibility of a layer."""
        pass
    
    @abstractmethod
    def toggle_layer(self, name):
        """Toggle the visibility of a layer."""
        pass
    
    @abstractmethod
    def get_cad_layers(self):
        """Return a list of CAD layer names and their visibility state."""
        pass

class AnimationObject:
    """
    Wrapper for a salabim animation object with visibility control.
    """
    def __init__(self, animate_obj, layer_name):
        self.animate_obj = animate_obj
        self.layer_name = layer_name
        self.visible = True
        self.original_kwargs = {}
        
        # Store original animation properties
        if hasattr(animate_obj, 'kwargs'):
            self.original_kwargs = animate_obj.kwargs.copy()
    
    def set_visibility(self, visible):
        """Toggle visibility of the animation object."""
        self.visible = visible
        
        # Implement visibility by manipulating alpha
        if hasattr(self.animate_obj, 'update'):
            if visible:
                # Restore original alpha
                if 'alpha0' in self.original_kwargs:
                    self.animate_obj.update(alpha0=self.original_kwargs['alpha0'])
                else:
                    self.animate_obj.update(alpha0=1)
            else:
                # Set alpha to 0 (invisible)
                self.animate_obj.update(alpha0=0)
        
        logger.debug(f"Visibility set to {visible} for {self.animate_obj} in layer {self.layer_name}")
    
    def show(self):
        """Show the animation object."""
        self.set_visibility(True)

    def hide(self):
        """Hide the animation object."""
        self.set_visibility(False)

class Layer:
    """
    Represents a visualization layer that can contain multiple animation objects.
    """
    def __init__(self, name, visible=True):
        self.name = name
        self.visible = visible
        self.objects = []
        self.is_cad_layer = False  # New flag to identify CAD layers
    
    def add_object(self, animate_obj):
        """Add an animation object to this layer."""
        obj = AnimationObject(animate_obj, self.name)
        self.objects.append(obj)
        # Set initial visibility based on layer state
        obj.set_visibility(self.visible)
        return obj
    
    def set_visibility(self, visible):
        """Set visibility for all objects in this layer."""
        self.visible = visible
        for obj in self.objects:
            obj.set_visibility(visible)
        logger.info(f"Layer {self.name} visibility set to {visible}")
    
    def toggle_visibility(self):
        """Toggle visibility of this layer."""
        self.set_visibility(not self.visible)
    
    def remove_object(self, animate_obj):
        """Remove an animation object from this layer."""
        for obj in self.objects[:]:
            if obj.animate_obj == animate_obj:
                self.objects.remove(obj)
                return True
        return False

class LayerManager(ILayerManager):
    """
    Manages multiple visualization layers for the simulation.
    """
    def __init__(self, env):
        self.env = env
        self.layers = {}
        self.cad_layers = set()  # Track CAD-specific layers
        
        # Create default layers
        self.create_layer("Background", True)
        self.create_layer("Units", True)
        self.create_layer("LadleCars", True)
        self.create_layer("Routes", True)
        self.create_layer("HUD", True)  # Heads-up display elements
    
    def create_layer(self, name, visible=True, is_cad_layer=False):
        """Create a new layer with the given name."""
        if name not in self.layers:
            self.layers[name] = Layer(name, visible)
            self.layers[name].is_cad_layer = is_cad_layer
            if is_cad_layer:
                self.cad_layers.add(name)
            logger.info(f"Layer created: {name} (CAD layer: {is_cad_layer})")
        return self.layers[name]
    
    def get_layer(self, name):
        """Get a layer by name, creating it if it doesn't exist."""
        if name not in self.layers:
            return self.create_layer(name)
        return self.layers[name]
    
    def add_object_to_layer(self, layer_name, animate_obj):
        """Add an animation object to the specified layer."""
        layer = self.get_layer(layer_name)
        return layer.add_object(animate_obj)
    
    def set_layer_visibility(self, name, visible):
        """Set the visibility of a layer."""
        if name in self.layers:
            self.layers[name].set_visibility(visible)
        else:
            logger.warning(f"Layer {name} not found.")
    
    def toggle_layer(self, name):
        """Toggle the visibility of a layer."""
        if name in self.layers:
            self.layers[name].toggle_visibility()
        else:
            logger.warning(f"Layer {name} not found.")
    
    def add_cad_layer(self, layer_name, visible=True):
        """
        Register a CAD layer for visualization control.
        
        Args:
            layer_name: Name of the CAD layer
            visible: Initial visibility state
        """
        if layer_name not in self.layers:
            layer = self.create_layer(layer_name, visible, is_cad_layer=True)
            logger.info(f"CAD Layer registered: {layer_name} (visible: {visible})")
        else:
            # Update visibility if layer already exists
            layer = self.layers[layer_name]
            layer.is_cad_layer = True
            layer.set_visibility(visible)
            if layer_name not in self.cad_layers:
                self.cad_layers.add(layer_name)
        return self.layers[layer_name]
    
    def get_cad_layers(self):
        """
        Return a list of CAD layer names and their visibility state.
        
        Returns:
            list of (layer_name, is_visible) tuples
        """
        return [(name, self.layers[name].visible) for name in self.cad_layers]
    
    def create_animation_on_layer(self, layer_name, anim_type, **kwargs):
        """
        Create an animation object on a specific layer.
        
        Args:
            layer_name: Name of the layer
            anim_type: Type of animation ('circle', 'rectangle', 'line', 'text', etc.)
            **kwargs: Arguments for the animation
        
        Returns:
            AnimationObject: The created animation object wrapper
        """
        animate_obj = None
        
        # Default to current environment if not specified
        if 'env' not in kwargs:
            kwargs['env'] = self.env
            
        # Create the appropriate animation based on type
        if anim_type == 'circle':
            animate_obj = sim.Animate(circle0=kwargs.pop('radius', 10), **kwargs)
        elif anim_type == 'rectangle':
            animate_obj = sim.Animate(rectangle0=kwargs.pop('rectangle', (-10, -10, 10, 10)), **kwargs)
        elif anim_type == 'line':
            animate_obj = sim.AnimateLine(spec=kwargs.pop('spec', (0, 0, 100, 100)), **kwargs)
        elif anim_type == 'text':
            animate_obj = sim.Animate(text=kwargs.pop('text', ''), **kwargs)
        else:
            logger.warning(f"Unknown animation type: {anim_type}")
            return None
        
        # Add to layer and return
        return self.add_object_to_layer(layer_name, animate_obj)

class CADLayerManagerWidget(QWidget):
    """
    Widget for managing CAD layer visibility.
    """
    layer_visibility_changed = pyqtSignal(str, bool)
    
    def __init__(self, layer_manager, parent=None):
        super().__init__(parent)
        self.layer_manager = layer_manager
        self.checkboxes = {}
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # Create a group box with a scroll area
        group_box = QGroupBox("CAD Layers")
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Content widget for the scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Add a label for instructions
        label = QLabel("Toggle visibility of CAD layers:")
        content_layout.addWidget(label)
        
        # Placeholder message when no CAD layers are available
        self.placeholder = QLabel("No CAD layers available")
        content_layout.addWidget(self.placeholder)
        
        # Container for checkboxes
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        content_layout.addWidget(self.checkbox_container)
        
        # Add stretch to push everything to the top
        content_layout.addStretch()
        
        # Set up the scroll area
        scroll_area.setWidget(content_widget)
        group_box_layout = QVBoxLayout(group_box)
        group_box_layout.addWidget(scroll_area)
        
        layout.addWidget(group_box)
        self.setLayout(layout)
        
        # Initial update
        self.update_layers()
    
    def update_layers(self):
        """Update the layer checkboxes based on the current CAD layers."""
        # Clear existing checkboxes
        for checkbox in self.checkboxes.values():
            self.checkbox_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.checkboxes.clear()
        
        # Get current CAD layers
        cad_layers = self.layer_manager.get_cad_layers()
        
        # Update placeholder visibility
        self.placeholder.setVisible(len(cad_layers) == 0)
        
        # Create checkboxes for each layer
        for layer_name, is_visible in cad_layers:
            checkbox = QCheckBox(layer_name)
            checkbox.setChecked(is_visible)
            checkbox.stateChanged.connect(lambda state, name=layer_name: 
                                           self.on_checkbox_changed(name, state > 0))
            self.checkboxes[layer_name] = checkbox
            self.checkbox_layout.addWidget(checkbox)
    
    def on_checkbox_changed(self, layer_name, checked):
        """Handle checkbox state changes."""
        self.layer_manager.set_layer_visibility(layer_name, checked)
        self.layer_visibility_changed.emit(layer_name, checked)