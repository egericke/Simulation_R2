"""
Interactive equipment layout editor for steel plant simulation.

This module provides a visual interface for placing equipment on the CAD layout
and defining their positions interactively.
"""

import os
import json
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QToolBar, QAction, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,
    QApplication, QMessageBox, QMenu, QFrame, QInputDialog, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt5.QtGui import (
    QIcon, QPainter, QPen, QBrush, QColor, QPixmap, QImage, 
    QFont, QFontMetrics, QPainterPath, QDrag, QTransform
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QSizeF, QMimeData, QByteArray, pyqtSignal, 
    QEvent, QSize
)
import logging

logger = logging.getLogger(__name__)

# Equipment types with their visual representations
EQUIPMENT_TYPES = {
    "EAF": {
        "color": QColor(255, 100, 100),  # Red
        "shape": "rect",
        "width": 80,
        "height": 80,
        "icon": "eaf.png",
        "description": "Electric Arc Furnace"
    },
    "LMF": {
        "color": QColor(100, 100, 255),  # Blue
        "shape": "rect",
        "width": 70,
        "height": 70,
        "icon": "lmf.png",
        "description": "Ladle Metallurgical Furnace"
    },
    "Degasser": {
        "color": QColor(100, 255, 100),  # Green
        "shape": "rect",
        "width": 60,
        "height": 60,
        "icon": "degasser.png",
        "description": "Vacuum Degasser"
    },
    "Caster": {
        "color": QColor(255, 200, 100),  # Orange
        "shape": "rect",
        "width": 100,
        "height": 50,
        "icon": "caster.png",
        "description": "Continuous Caster"
    },
    "LadleCar": {
        "color": QColor(200, 100, 255),  # Purple
        "shape": "rect",
        "width": 30,
        "height": 20,
        "icon": "ladle_car.png",
        "description": "Ladle Car"
    },
    "Crane": {
        "color": QColor(255, 255, 100),  # Yellow
        "shape": "rect",
        "width": 40,
        "height": 30,
        "icon": "crane.png",
        "description": "Overhead Crane"
    },
    "LadlePreheater": {
        "color": QColor(255, 130, 70),  # Orange-red
        "shape": "rect",
        "width": 50,
        "height": 50,
        "icon": "preheater.png",
        "description": "Ladle Preheater"
    },
    "SlagDump": {
        "color": QColor(139, 69, 19),  # Brown
        "shape": "rect",
        "width": 60,
        "height": 40,
        "icon": "slag_dump.png",
        "description": "Slag Dump Area"
    },
    "RoutePoint": {
        "color": QColor(120, 120, 120),  # Gray
        "shape": "ellipse",
        "width": 20,
        "height": 20,
        "icon": "route_point.png",
        "description": "Route Connection Point"
    }
}

class EquipmentItem(QGraphicsItem):
    """A draggable equipment item for the layout scene."""
    
    def __init__(self, equipment_type, item_id, bay_name, x, y, width=None, height=None, parent=None):
        super().__init__(parent)
        self.equipment_type = equipment_type
        self.item_id = item_id
        self.bay_name = bay_name
        
        # Get equipment properties
        eq_props = EQUIPMENT_TYPES.get(equipment_type, EQUIPMENT_TYPES["EAF"])
        self.width = width if width is not None else eq_props["width"]
        self.height = height if height is not None else eq_props["height"]
        self.color = eq_props["color"]
        self.shape = eq_props["shape"]
        
        # Set position
        self.setPos(x, y)
        
        # Make item draggable and selectable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # Set tool tip
        self.setToolTip(f"{eq_props['description']}\nID: {item_id}\nBay: {bay_name}\nSize: {self.width}x{self.height}")
    
    def boundingRect(self):
        """Define the bounding rectangle for the item."""
        return QRectF(-self.width/2, -self.height/2, self.width, self.height)
    
    def paint(self, painter, option, widget):
        """Paint the equipment item."""
        rect = self.boundingRect()
        
        if self.isSelected():
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.setBrush(QBrush(self.color.lighter(120)))
        else:
            painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
            painter.setBrush(QBrush(self.color))
        
        if self.shape == "rect":
            painter.drawRect(rect)
        elif self.shape == "ellipse":
            painter.drawEllipse(rect)
        
        painter.setPen(QPen(Qt.black))
        painter.setFont(QFont("Arial", 8))
        label = f"{self.equipment_type} {self.item_id}"
        painter.drawText(rect, Qt.AlignCenter, label)
    
    def itemChange(self, change, value):
        """Handle item changes, particularly position changes."""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            grid_size = 10
            new_pos.setX(round(new_pos.x() / grid_size) * grid_size)
            new_pos.setY(round(new_pos.y() / grid_size) * grid_size)
            if hasattr(self.scene(), "position_changed"):
                self.scene().position_changed.emit(self)
            return new_pos
        return super().itemChange(change, value)
    
    def get_data(self):
        """Get the item's data as a dictionary."""
        pos = self.pos()
        return {
            "type": self.equipment_type,
            "id": self.item_id,
            "bay": self.bay_name,
            "x": pos.x(),
            "y": pos.y(),
            "width": self.width,
            "height": self.height
        }

class RoutePointItem(QGraphicsItem):
    """A route connection point item for creating arbitrary routing paths."""
    
    def __init__(self, point_id, x, y, parent=None):
        super().__init__(parent)
        self.point_id = point_id
        self.width = EQUIPMENT_TYPES["RoutePoint"]["width"]
        self.height = EQUIPMENT_TYPES["RoutePoint"]["height"]
        self.color = EQUIPMENT_TYPES["RoutePoint"]["color"]
        
        # Set position
        self.setPos(x, y)
        
        # Make item draggable and selectable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # Set tool tip
        self.setToolTip(f"Route Point {point_id}\nPosition: ({x}, {y})")
    
    def boundingRect(self):
        """Define the bounding rectangle for the item."""
        return QRectF(-self.width/2, -self.height/2, self.width, self.height)
    
    def paint(self, painter, option, widget):
        """Paint the route point item."""
        rect = self.boundingRect()
        
        if self.isSelected():
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.setBrush(QBrush(self.color.lighter(120)))
        else:
            painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
            painter.setBrush(QBrush(self.color))
        
        painter.drawEllipse(rect)
        
        painter.setPen(QPen(Qt.black))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(rect, Qt.AlignCenter, str(self.point_id))
    
    def itemChange(self, change, value):
        """Handle item changes, particularly position changes."""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            grid_size = 10
            new_pos.setX(round(new_pos.x() / grid_size) * grid_size)
            new_pos.setY(round(new_pos.y() / grid_size) * grid_size)
            if hasattr(self.scene(), "position_changed"):
                self.scene().position_changed.emit(self)
            return new_pos
        return super().itemChange(change, value)
    
    def get_data(self):
        """Get the route point's data as a dictionary."""
        pos = self.pos()
        return {
            "type": "RoutePoint",
            "id": self.point_id,
            "x": pos.x(),
            "y": pos.y()
        }

class RoutePathItem(QGraphicsPathItem):
    """A path item for ladle car or crane routes."""
    
    def __init__(self, start_item, end_item, route_type="LadleCar", transit_time=10, parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.route_type = route_type
        self.transit_time = transit_time
        
        # Different styling based on route type
        if route_type == "LadleCar":
            color = QColor(100, 100, 255)  # Blue
            style = Qt.DashLine
            width = 3
        elif route_type == "Crane":
            color = QColor(255, 200, 100)  # Orange
            style = Qt.DotLine
            width = 3
        elif route_type == "Ladle":
            color = QColor(200, 0, 0)  # Dark red
            style = Qt.SolidLine
            width = 4
        else:
            color = QColor(100, 100, 100)  # Gray
            style = Qt.DashDotLine
            width = 2
        
        self.setPen(QPen(color, width, style))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.update_path()
        
        # Set tooltip
        self.setToolTip(f"{route_type} Route\nFrom: {self.get_start_name()}\nTo: {self.get_end_name()}\nTransit Time: {transit_time} min")
    
    def get_start_name(self):
        """Get a readable name for the start item."""
        if hasattr(self.start_item, 'equipment_type'):
            return f"{self.start_item.equipment_type} {self.start_item.item_id}"
        elif hasattr(self.start_item, 'point_id'):
            return f"Point {self.start_item.point_id}"
        return "Unknown"
    
    def get_end_name(self):
        """Get a readable name for the end item."""
        if hasattr(self.end_item, 'equipment_type'):
            return f"{self.end_item.equipment_type} {self.end_item.item_id}"
        elif hasattr(self.end_item, 'point_id'):
            return f"Point {self.end_item.point_id}"
        return "Unknown"
    
    def update_path(self):
        """Update the path between the connected items."""
        if not self.start_item or not self.end_item:
            return
        
        path = QPainterPath()
        start_pos = self.start_item.pos()
        end_pos = self.end_item.pos()
        
        # Draw a curved path
        path.moveTo(start_pos)
        
        # Calculate control points for a smooth curve
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        dist = (dx**2 + dy**2)**0.5
        
        # Adjust control points based on distance between points
        if dist < 100:
            # For short distances, make a simple curve
            control1 = QPointF(start_pos.x() + dx/3, start_pos.y() + dy/3)
            control2 = QPointF(start_pos.x() + 2*dx/3, start_pos.y() + 2*dy/3)
        else:
            # For longer distances, make a more pronounced curve
            control1 = QPointF(start_pos.x() + dx/3, start_pos.y())
            control2 = QPointF(start_pos.x() + 2*dx/3, end_pos.y())
        
        path.cubicTo(control1, control2, end_pos)
        self.setPath(path)
    
    def get_data(self):
        """Get the route path data as a dictionary."""
        # Determine start item key
        if hasattr(self.start_item, 'equipment_type'):
            start_key = f"{self.start_item.equipment_type}_{self.start_item.item_id}"
        elif hasattr(self.start_item, 'point_id'):
            start_key = f"RoutePoint_{self.start_item.point_id}"
        else:
            start_key = "unknown"
        
        # Determine end item key
        if hasattr(self.end_item, 'equipment_type'):
            end_key = f"{self.end_item.equipment_type}_{self.end_item.item_id}"
        elif hasattr(self.end_item, 'point_id'):
            end_key = f"RoutePoint_{self.end_item.point_id}"
        else:
            end_key = "unknown"
            
        return {
            "type": self.route_type,
            "start_item": start_key,
            "end_item": end_key,
            "transit_time": self.transit_time
        }

class BayItem(QGraphicsItem):
    """A graphical item representing a bay in the layout scene."""
    def __init__(self, name, x, y, width, height, parent=None):
        super().__init__(parent)
        self.name = name
        self.rect = QRectF(0, 0, width, height)
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

    def boundingRect(self):
        return self.rect.adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget):
        painter.setBrush(QBrush(QColor(0, 255, 0, 50)))  # Semi-transparent green
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(self.rect)
        painter.drawText(self.rect, Qt.AlignCenter, self.name)

    def get_data(self):
        pos = self.pos()
        return {
            "name": self.name,
            "x": pos.x(),
            "y": pos.y(),
            "width": self.rect.width(),
            "height": self.rect.height()
        }

class LayoutScene(QGraphicsScene):
    """Custom scene for the equipment layout."""
    
    position_changed = pyqtSignal(object)  # Changed to accept any item
    selection_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 2000, 1500)
        self.grid_size = 20
        self.show_grid = True
        self.route_mode = False
        self.route_start_item = None
        self.route_type = "LadleCar"
        self.background_image = None
        
        # Route Points - Dict of route point ID to route point item
        self.route_points = {}
        self.next_route_point_id = 1
        
        # Bay-related properties
        self.bay_mode = False
        self.bay_items = []
        self.temp_bay_rect = None
        self.bay_start_pos = None
        
        # Visualization properties
        self.show_ladle_flows = True
        self.ladle_anim_timer = None
        self.animation_step = 0
        
        # Route definitions for simulation visualization
        self.route_paths = []
    
    def drawBackground(self, painter, rect):
        """Draw scene background with grid."""
        super().drawBackground(painter, rect)
        if self.background_image:
            painter.drawImage(self.sceneRect(), self.background_image)
        if self.show_grid:
            left = int(rect.left()) - (int(rect.left()) % self.grid_size)
            top = int(rect.top()) - (int(rect.top()) % self.grid_size)
            right = int(rect.right())
            bottom = int(rect.bottom())
            painter.setPen(QPen(QColor(200, 200, 200, 100), 1))
            for x in range(left, right, self.grid_size):
                painter.drawLine(x, top, x, bottom)
            for y in range(top, bottom, self.grid_size):
                painter.drawLine(left, y, right, y)
    
    def set_background_image(self, image_path):
        """Set the background image from a file."""
        if not image_path or not os.path.exists(image_path):
            self.background_image = None
            return False
        try:
            image = QImage(image_path)
            if image.isNull():
                return False
            self.background_image = image
            return True
        except Exception as e:
            logger.error(f"Error loading background image: {e}")
            return False
    
    def add_equipment(self, equipment_type, item_id, bay_name, x, y, width=None, height=None):
        """Add a new equipment item to the scene."""
        item = EquipmentItem(equipment_type, item_id, bay_name, x, y, width, height)
        self.addItem(item)
        return item
    
    def add_route_point(self, x, y, point_id=None):
        """Add a new route point to the scene."""
        if point_id is None:
            point_id = self.next_route_point_id
            self.next_route_point_id += 1
        
        item = RoutePointItem(point_id, x, y)
        self.addItem(item)
        self.route_points[point_id] = item
        return item
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.LeftButton and self.route_mode:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, (EquipmentItem, RoutePointItem)):
                self.route_start_item = item
                event.accept()
                return
        elif self.bay_mode and event.button() == Qt.LeftButton:
            self.bay_start_pos = event.scenePos()
            self.temp_bay_rect = QGraphicsRectItem()
            self.temp_bay_rect.setPen(QPen(Qt.red, 2, Qt.DashLine))
            self.addItem(self.temp_bay_rect)
            event.accept()
            return
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.LeftButton and self.route_mode and self.route_start_item:
            end_item = self.itemAt(event.scenePos(), QTransform())
            
            # Check if we need to create a route point
            if not isinstance(end_item, (EquipmentItem, RoutePointItem)) or end_item == self.route_start_item:
                # Create a route point at mouse position
                pos = event.scenePos()
                end_item = self.add_route_point(pos.x(), pos.y())
                
            # Create the route between the two items
            if self.route_start_item != end_item:
                route = RoutePathItem(self.route_start_item, end_item, self.route_type)
                self.addItem(route)
                self.route_paths.append(route)
                event.accept()
            
            self.route_start_item = None
            return
            
        elif self.bay_mode and self.bay_start_pos:
            end_pos = event.scenePos()
            rect = QRectF(self.bay_start_pos, end_pos).normalized()
            if rect.width() > 10 and rect.height() > 10:
                name, ok = QInputDialog.getText(None, "Bay Name", "Enter bay name:")
                if ok and name:
                    self.removeItem(self.temp_bay_rect)
                    bay = BayItem(name, rect.x(), rect.y(), rect.width(), rect.height())
                    self.addItem(bay)
                    self.bay_items.append(bay)
                    QApplication.instance().activeWindow().update_bay_combo()
            self.bay_start_pos = None
            self.temp_bay_rect = None
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        if self.route_mode and self.route_start_item:
            update_rect = QRectF(self.route_start_item.pos(), event.scenePos()).normalized()
            update_rect = update_rect.adjusted(-10, -10, 10, 10)
            self.update(update_rect)
        elif self.bay_mode and self.bay_start_pos:
            end_pos = event.scenePos()
            rect = QRectF(self.bay_start_pos, end_pos).normalized()
            self.temp_bay_rect.setRect(rect)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def get_equipment_data(self):
        """Get data for all equipment items in the scene."""
        equipment_data = []
        for item in self.items():
            if isinstance(item, EquipmentItem):
                equipment_data.append(item.get_data())
        return equipment_data
    
    def get_route_data(self):
        """Get data for all route paths in the scene."""
        route_data = []
        for item in self.items():
            if isinstance(item, RoutePathItem):
                route_data.append(item.get_data())
        return route_data
    
    def get_route_point_data(self):
        """Get data for all route points in the scene."""
        point_data = []
        for item in self.items():
            if isinstance(item, RoutePointItem):
                point_data.append(item.get_data())
        return point_data
    
    def get_bay_data(self):
        """Get data for all bays in the scene."""
        return [bay.get_data() for bay in self.bay_items]
    
    def clear_selection(self):
        """Clear all selected items."""
        for item in self.selectedItems():
            item.setSelected(False)
    
    def delete_selected_items(self):
        """Delete all selected items."""
        selected_items = self.selectedItems().copy()  # Make a copy since we'll modify the selection
        for item in selected_items:
            if isinstance(item, BayItem):
                self.bay_items.remove(item)
            
            # Remove route paths connected to this item if it's equipment or route point
            if isinstance(item, (EquipmentItem, RoutePointItem)):
                connected_routes = []
                for path in self.route_paths:
                    if path.start_item == item or path.end_item == item:
                        connected_routes.append(path)
                
                for path in connected_routes:
                    self.route_paths.remove(path)
                    self.removeItem(path)
            
            # Remove route point from dictionary
            if isinstance(item, RoutePointItem):
                if item.point_id in self.route_points:
                    del self.route_points[item.point_id]
            
            # Remove the path from route_paths if it's a route
            if isinstance(item, RoutePathItem) and item in self.route_paths:
                self.route_paths.remove(item)
                
            self.removeItem(item)
    
    def set_route_mode(self, enabled, route_type="LadleCar"):
        """Enable or disable route creation mode."""
        self.route_mode = enabled
        self.route_type = route_type
        self.bay_mode = False if enabled else self.bay_mode
        view = self.views()[0] if self.views() else None
        if view:
            view.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
    
    def set_bay_mode(self, enabled):
        """Toggle bay drawing mode."""
        self.bay_mode = enabled
        self.route_mode = False if enabled else self.route_mode
        view = self.views()[0] if self.views() else None
        if view:
            view.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
    
    def update_route_paths(self):
        """Update all route paths to reflect any position changes."""
        for item in self.items():
            if isinstance(item, RoutePathItem):
                item.update_path()

class LayoutView(QGraphicsView):
    """Custom view for the equipment layout scene."""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.zoom_factor = 1.2
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.current_zoom = 1.0
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        zoom_in = event.angleDelta().y() > 0
        factor = self.zoom_factor if zoom_in else 1.0 / self.zoom_factor
        new_zoom = self.current_zoom * factor
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return
        self.current_zoom = new_zoom
        self.scale(factor, factor)
    
    def fit_scene(self):
        """Fit the entire scene in the view."""
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        view_rect = self.viewport().rect()
        scene_rect = self.scene().sceneRect()
        x_ratio = view_rect.width() / scene_rect.width()
        y_ratio = view_rect.height() / scene_rect.height()
        self.current_zoom = min(x_ratio, y_ratio)
    
    def reset_zoom(self):
        """Reset to original zoom level."""
        self.setTransform(QTransform())
        self.current_zoom = 1.0
    
    def contextMenuEvent(self, event):
        """Show context menu on right-click."""
        menu = QMenu(self)
        fit_action = menu.addAction("Fit Scene to View")
        reset_action = menu.addAction("Reset Zoom")
        menu.addSeparator()
        item = self.scene().itemAt(self.mapToScene(event.pos()), QTransform())
        if item:
            if isinstance(item, EquipmentItem):
                menu.addAction("Properties...")
                delete_action = menu.addAction("Delete Equipment")
            elif isinstance(item, RoutePathItem):
                menu.addAction("Route Properties...")
                delete_action = menu.addAction("Delete Route")
            elif isinstance(item, RoutePointItem):
                menu.addAction("Route Point Properties...")
                delete_action = menu.addAction("Delete Route Point")
            elif isinstance(item, BayItem):
                menu.addAction("Bay Properties...")
                delete_action = menu.addAction("Delete Bay")
            
            # Add a route point here
            add_point_action = menu.addAction("Add Route Point Here")
        else:
            # Add a route point at this position
            add_point_action = menu.addAction("Add Route Point Here")
        
        action = menu.exec_(event.globalPos())
        if action == fit_action:
            self.fit_scene()
        elif action == reset_action:
            self.reset_zoom()
        elif action and action.text() == "Add Route Point Here":
            pos = self.mapToScene(event.pos())
            self.scene().add_route_point(pos.x(), pos.y())
        elif action and action.text() in ["Delete Equipment", "Delete Route", "Delete Route Point", "Delete Bay"]:
            self.scene().removeItem(item)
            if isinstance(item, BayItem):
                self.scene().bay_items.remove(item)
                QApplication.instance().activeWindow().update_bay_combo()
            elif isinstance(item, RoutePointItem):
                if item.point_id in self.scene().route_points:
                    del self.scene().route_points[item.point_id]
            elif isinstance(item, RoutePathItem) and item in self.scene().route_paths:
                self.scene().route_paths.remove(item)

class RouteSimulator(QWidget):
    """Widget for visualizing ladle flow and simulating ladle car routes."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
        self.play_button.clicked.connect(self.toggle_simulation)
        controls_layout.addWidget(self.play_button)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_simulation)
        controls_layout.addWidget(self.reset_button)
        
        self.speed_label = QLabel("Speed:")
        controls_layout.addWidget(self.speed_label)
        
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 10)
        self.speed_spin.setValue(5)
        controls_layout.addWidget(self.speed_spin)
        
        controls_layout.addStretch()
        self.layout.addLayout(controls_layout)
        
        # Routes list
        routes_group = QGroupBox("Ladle Flow Routes")
        routes_layout = QVBoxLayout()
        
        self.routes_list = QListWidget()
        routes_layout.addWidget(self.routes_list)
        
        # Add route button
        add_route_button = QPushButton("Add Ladle Flow Route")
        add_route_button.clicked.connect(self.add_ladle_flow_route)
        routes_layout.addWidget(add_route_button)
        
        routes_group.setLayout(routes_layout)
        self.layout.addWidget(routes_group)
        
        # Internal properties
        self.scene = None
        self.is_playing = False
        self.ladle_positions = {}  # Maps route ID to current position (0-1)
        self.ladle_speeds = {}     # Maps route ID to speed
    
    def set_scene(self, scene):
        """Set the scene reference for route visualization."""
        self.scene = scene
        self.update_routes_list()
    
    def update_routes_list(self):
        """Update the routes list from the scene."""
        if not self.scene:
            return
            
        self.routes_list.clear()
        
        for i, route in enumerate(self.scene.route_paths):
            route_name = f"Route {i+1}: {route.get_start_name()} → {route.get_end_name()}"
            item = QListWidgetItem(route_name)
            item.setData(Qt.UserRole, route)
            self.routes_list.addItem(item)
            
            # Initialize positions
            self.ladle_positions[id(route)] = 0.0
            self.ladle_speeds[id(route)] = 0.01 * self.speed_spin.value()
    
    def add_ladle_flow_route(self):
        """Add a ladle flow route for visualization."""
        if not self.scene:
            return
            
        selected_items = self.scene.selectedItems()
        if len(selected_items) != 2:
            QMessageBox.warning(self, "Selection Error", 
                               "You must select exactly two items (equipment or route points) to create a ladle flow route.")
            return
            
        start_item, end_item = selected_items
        if not (isinstance(start_item, (EquipmentItem, RoutePointItem)) and 
                isinstance(end_item, (EquipmentItem, RoutePointItem))):
            QMessageBox.warning(self, "Selection Error", 
                               "Both selected items must be equipment or route points.")
            return
            
        # Create a ladle flow route
        route = RoutePathItem(start_item, end_item, "Ladle")
        self.scene.addItem(route)
        self.scene.route_paths.append(route)
        
        # Update the routes list
        self.update_routes_list()
    
    def toggle_simulation(self):
        """Toggle the simulation play/pause state."""
        self.is_playing = not self.is_playing
        self.play_button.setText("Pause" if self.is_playing else "Play")
        self.play_button.setStyleSheet(
            "background-color: #f44336; color: white; font-size: 14px; padding: 5px;" if self.is_playing else
            "background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;"
        )
        
        # Start/stop the animation timer
        if self.is_playing:
            self.start_animation()
        else:
            self.stop_animation()
    
    def reset_simulation(self):
        """Reset the simulation to its initial state."""
        for route_id in self.ladle_positions:
            self.ladle_positions[route_id] = 0.0
        
        # Redraw the scene
        if self.scene:
            self.scene.update()
    
    def start_animation(self):
        """Start the animation timer."""
        if not hasattr(self, 'timer') or self.timer is None:
            from PyQt5.QtCore import QTimer
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_animation)
        
        self.timer.start(50)  # 20 fps
    
    def stop_animation(self):
        """Stop the animation timer."""
        if hasattr(self, 'timer') and self.timer is not None:
            self.timer.stop()
    
    def update_animation(self):
        """Update the animation state."""
        if not self.scene or not self.is_playing:
            return
            
        # Update ladle positions
        for route in self.scene.route_paths:
            route_id = id(route)
            if route_id in self.ladle_positions:
                self.ladle_positions[route_id] += self.ladle_speeds[route_id]
                if self.ladle_positions[route_id] > 1.0:
                    self.ladle_positions[route_id] = 0.0
        
        # Redraw the scene
        self.scene.update()

class EquipmentLayoutEditor(QDialog):
    """Dialog for editing the equipment layout."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.layout_modified = False
        self.setWindowTitle("Equipment Layout Editor")
        self.setMinimumSize(1200, 800)
        self.create_ui()
        self.load_layout_data()
    
    def create_ui(self):
        """Create the user interface."""
        main_layout = QVBoxLayout()
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        
        save_action = QAction(QIcon.fromTheme("document-save", QIcon("icons/save.png")), "Save Layout", self)
        save_action.triggered.connect(self.save_layout)
        toolbar.addAction(save_action)
        
        load_action = QAction(QIcon.fromTheme("document-open", QIcon("icons/open.png")), "Load Layout", self)
        load_action.triggered.connect(self.load_layout)
        toolbar.addAction(load_action)
        
        toolbar.addSeparator()
        
        grid_action = QAction(QIcon.fromTheme("view-grid", QIcon("icons/grid.png")), "Toggle Grid", self)
        grid_action.setCheckable(True)
        grid_action.setChecked(True)
        grid_action.triggered.connect(self.toggle_grid)
        toolbar.addAction(grid_action)
        
        fit_action = QAction(QIcon.fromTheme("zoom-fit-best", QIcon("icons/fit.png")), "Fit View", self)
        fit_action.triggered.connect(self.fit_view)
        toolbar.addAction(fit_action)
        
        toolbar.addSeparator()
        
        self.route_action = QAction(QIcon.fromTheme("draw-line", QIcon("icons/route.png")), "Add Routes", self)
        self.route_action.setCheckable(True)
        self.route_action.triggered.connect(self.toggle_route_mode)
        toolbar.addAction(self.route_action)
        
        # Add Bay Drawing Action
        self.bay_action = QAction(QIcon.fromTheme("draw-rectangle", QIcon("icons/bay.png")), "Add Bay", self)
        self.bay_action.setCheckable(True)
        self.bay_action.triggered.connect(self.toggle_bay_mode)
        toolbar.addAction(self.bay_action)
        
        toolbar.addSeparator()
        
        delete_action = QAction(QIcon.fromTheme("edit-delete", QIcon("icons/delete.png")), "Delete Selected", self)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)
        
        # Add Route Point Action
        add_point_action = QAction(QIcon.fromTheme("list-add", QIcon("icons/add_point.png")), "Add Route Point", self)
        add_point_action.triggered.connect(self.add_route_point)
        toolbar.addAction(add_point_action)
        
        main_layout.addWidget(toolbar)
        
        # Create a splitter for the main layout
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Scene and view
        self.scene = LayoutScene()
        self.view = LayoutView(self.scene)
        splitter.addWidget(self.view)
        
        # Right side: Tools panel with tabs
        tools_panel = QWidget()
        tools_layout = QVBoxLayout(tools_panel)
        
        # Equipment configuration group
        eq_group = QGroupBox("Add Equipment")
        eq_layout = QVBoxLayout()
        
        eq_layout.addWidget(QLabel("Equipment Type:"))
        self.eq_type_combo = QComboBox()
        for eq_type, props in EQUIPMENT_TYPES.items():
            # Skip route point, it's added differently
            if eq_type != "RoutePoint":
                self.eq_type_combo.addItem(props["description"], eq_type)
        eq_layout.addWidget(self.eq_type_combo)
        
        eq_layout.addWidget(QLabel("Bay:"))
        self.bay_combo = QComboBox()
        eq_layout.addWidget(self.bay_combo)
        
        eq_layout.addWidget(QLabel("ID:"))
        self.id_spin = QSpinBox()
        self.id_spin.setRange(0, 99)
        eq_layout.addWidget(self.id_spin)
        
        # Add width and height fields
        eq_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(10, 500)
        self.width_spin.setValue(EQUIPMENT_TYPES["EAF"]["width"])
        eq_layout.addWidget(self.width_spin)
        
        eq_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(10, 500)
        self.height_spin.setValue(EQUIPMENT_TYPES["EAF"]["height"])
        eq_layout.addWidget(self.height_spin)
        
        # Update width/height when equipment type changes
        self.eq_type_combo.currentIndexChanged.connect(self.update_size_defaults)
        
        add_button = QPushButton("Add to Layout")
        add_button.clicked.connect(self.add_equipment)
        add_button.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
        eq_layout.addWidget(add_button)
        
        eq_group.setLayout(eq_layout)
        tools_layout.addWidget(eq_group)
        
        # Routes group
        routes_group = QGroupBox("Routes")
        routes_layout = QVBoxLayout()
        
        routes_layout.addWidget(QLabel("Route Type:"))
        self.route_type_combo = QComboBox()
        self.route_type_combo.addItem("Ladle Car Route", "LadleCar")
        self.route_type_combo.addItem("Crane Route", "Crane")
        self.route_type_combo.addItem("Ladle Flow", "Ladle")
        routes_layout.addWidget(self.route_type_combo)
        
        route_info_label = QLabel(
            "To add a route:\n"
            "1. Click 'Add Routes' in toolbar\n"
            "2. Click on start equipment or route point\n"
            "3. Click on end equipment, route point, or empty space to create a route point\n"
            "\nFor ladle flow visualization, add route points at key locations and connect them with Ladle Flow routes."
        )
        route_info_label.setWordWrap(True)
        routes_layout.addWidget(route_info_label)
        
        routes_group.setLayout(routes_layout)
        tools_layout.addWidget(routes_group)
        
        # Add Bay Section
        bay_group = QGroupBox("Bays")
        bay_layout = QVBoxLayout()
        
        bay_info_label = QLabel(
            "To add a bay:\n"
            "1. Click 'Add Bay' in toolbar\n"
            "2. Click and drag to draw bay\n"
            "3. Enter bay name when prompted"
        )
        bay_info_label.setWordWrap(True)
        bay_layout.addWidget(bay_info_label)
        
        bay_group.setLayout(bay_layout)
        tools_layout.addWidget(bay_group)
        
        # Properties group for selected items
        props_group = QGroupBox("Selected Item Properties")
        props_layout = QVBoxLayout()
        
        self.props_label = QLabel("No item selected")
        props_layout.addWidget(self.props_label)
        
        props_layout.addWidget(QLabel("X Position:"))
        self.pos_x_spin = QSpinBox()
        self.pos_x_spin.setRange(0, 5000)
        self.pos_x_spin.valueChanged.connect(self.update_selected_position)
        props_layout.addWidget(self.pos_x_spin)
        
        props_layout.addWidget(QLabel("Y Position:"))
        self.pos_y_spin = QSpinBox()
        self.pos_y_spin.setRange(0, 5000)
        self.pos_y_spin.valueChanged.connect(self.update_selected_position)
        props_layout.addWidget(self.pos_y_spin)
        
        # Add width and height properties for selected item
        props_layout.addWidget(QLabel("Width:"))
        self.props_width_spin = QSpinBox()
        self.props_width_spin.setRange(10, 500)
        self.props_width_spin.valueChanged.connect(self.update_selected_size)
        props_layout.addWidget(self.props_width_spin)
        
        props_layout.addWidget(QLabel("Height:"))
        self.props_height_spin = QSpinBox()
        self.props_height_spin.setRange(10, 500)
        self.props_height_spin.valueChanged.connect(self.update_selected_size)
        props_layout.addWidget(self.props_height_spin)
        
        # Transit time for routes
        props_layout.addWidget(QLabel("Transit Time (min):"))
        self.transit_time_spin = QSpinBox()
        self.transit_time_spin.setRange(1, 120)
        self.transit_time_spin.setValue(10)
        self.transit_time_spin.valueChanged.connect(self.update_selected_transit_time)
        props_layout.addWidget(self.transit_time_spin)
        
        props_group.setLayout(props_layout)
        tools_layout.addWidget(props_group)
        
        # Background group
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout()
        
        load_bg_button = QPushButton("Load CAD Drawing")
        load_bg_button.clicked.connect(self.load_background)
        load_bg_button.setStyleSheet("background-color: #2196F3; color: white; font-size: 14px; padding: 5px;")
        bg_layout.addWidget(load_bg_button)
        
        self.bg_path_label = QLabel("No background loaded")
        self.bg_path_label.setWordWrap(True)
        bg_layout.addWidget(self.bg_path_label)
        
        bg_group.setLayout(bg_layout)
        tools_layout.addWidget(bg_group)
        
        # Add route simulation widget
        self.route_simulator = RouteSimulator()
        self.route_simulator.set_scene(self.scene)
        tools_layout.addWidget(self.route_simulator)
        
        tools_layout.addStretch()
        splitter.addWidget(tools_panel)
        
        # Set initial sizes
        splitter.setSizes([800, 400])
        main_layout.addWidget(splitter)
        
        # Bottom bar with status and buttons
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        ok_button = QPushButton("Save and Close")
        ok_button.clicked.connect(self.accept)
        ok_button.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
        button_layout.addWidget(ok_button)
        
        status_layout.addLayout(button_layout)
        main_layout.addLayout(status_layout)
        
        self.setLayout(main_layout)
        
        # Connect signals
        self.scene.position_changed.connect(self.update_property_panel)
        self.scene.selectionChanged.connect(self.selection_changed)
        self.route_type_combo.currentIndexChanged.connect(self.update_route_type)
    
    def update_size_defaults(self):
        """Update the width and height fields based on the selected equipment type."""
        eq_type = self.eq_type_combo.currentData()
        if eq_type in EQUIPMENT_TYPES:
            self.width_spin.setValue(EQUIPMENT_TYPES[eq_type]["width"])
            self.height_spin.setValue(EQUIPMENT_TYPES[eq_type]["height"])
    
    def load_layout_data(self):
        """Load layout data from configuration."""
        # Load bays
        bays = self.config.get("bays", {})
        self.bay_combo.clear()
        for bay_name, bay_data in bays.items():
            self.bay_combo.addItem(bay_name)
            if all(k in bay_data for k in ("x", "y", "width", "height")):
                bay = BayItem(bay_name, bay_data["x"], bay_data["y"], bay_data["width"], bay_data["height"])
                self.scene.addItem(bay)
                self.scene.bay_items.append(bay)
        
        # Load equipment
        equipment_positions = self.config.get("equipment_positions", {})
        for key, position in equipment_positions.items():
            eq_type = position.get("type", "EAF")
            eq_id = position.get("id", 0)
            bay = position.get("bay", "bay1")
            x = position.get("x", 0)
            y = position.get("y", 0)
            width = position.get("width", EQUIPMENT_TYPES.get(eq_type, {}).get("width"))
            height = position.get("height", EQUIPMENT_TYPES.get(eq_type, {}).get("height"))
            self.scene.add_equipment(eq_type, eq_id, bay, x, y, width, height)
        
        # Load route points
        route_points = self.config.get("route_points", {})
        for point_id_str, point_data in route_points.items():
            try:
                point_id = int(point_id_str)
                x = point_data.get("x", 0)
                y = point_data.get("y", 0)
                point = self.scene.add_route_point(x, y, point_id)
                
                # Update next point ID if needed
                if point_id >= self.scene.next_route_point_id:
                    self.scene.next_route_point_id = point_id + 1
            except (ValueError, TypeError) as e:
                logger.error(f"Error loading route point {point_id_str}: {e}")
        
        # Load routes
        routes = self.config.get("routes", [])
        for route_data in routes:
            route_type = route_data.get("type", "LadleCar")
            start_item_key = route_data.get("start_item", "")
            end_item_key = route_data.get("end_item", "")
            transit_time = route_data.get("transit_time", 10)
            
            # Find the start and end items
            start_item = end_item = None
            
            # Check if keys refer to route points
            if start_item_key.startswith("RoutePoint_"):
                try:
                    point_id = int(start_item_key.split("_")[1])
                    if point_id in self.scene.route_points:
                        start_item = self.scene.route_points[point_id]
                except (ValueError, IndexError):
                    pass
            
            if end_item_key.startswith("RoutePoint_"):
                try:
                    point_id = int(end_item_key.split("_")[1])
                    if point_id in self.scene.route_points:
                        end_item = self.scene.route_points[point_id]
                except (ValueError, IndexError):
                    pass
            
            # Check for equipment if not found as route point
            if not start_item or not end_item:
                for item in self.scene.items():
                    if isinstance(item, EquipmentItem):
                        item_key = f"{item.equipment_type}_{item.item_id}"
                        if item_key == start_item_key:
                            start_item = item
                        elif item_key == end_item_key:
                            end_item = item
            
            # Create the route if both items were found
            if start_item and end_item:
                route = RoutePathItem(start_item, end_item, route_type, transit_time)
                self.scene.addItem(route)
                self.scene.route_paths.append(route)
        
        # Load background
        cad_file = self.config.get("cad_file_path", None)
        background_image = self.config.get("background_image", None)
        
        # Prefer bitmap image if available
        if background_image and os.path.exists(background_image):
            self.scene.set_background_image(background_image)
            self.bg_path_label.setText(os.path.basename(background_image))
        elif cad_file and os.path.exists(cad_file):
            _, ext = os.path.splitext(cad_file)
            if ext.lower() != ".dxf":
                self.scene.set_background_image(cad_file)
                self.bg_path_label.setText(os.path.basename(cad_file))
        
        self.view.fit_scene()
        
        # Update the route simulator
        self.route_simulator.update_routes_list()
    
    def save_layout(self):
        """Save the current layout to configuration."""
        # Save equipment positions
        equipment_positions = {}
        for item_data in self.scene.get_equipment_data():
            key = f"{item_data['type']}_{item_data['id']}_{item_data['bay']}"
            equipment_positions[key] = item_data
        
        # Save route points
        route_points = {}
        for point_data in self.scene.get_route_point_data():
            point_id = point_data['id']
            route_points[str(point_id)] = point_data
        
        # Save routes
        routes = self.scene.get_route_data()
        
        # Save bays
        bays = {bay["name"]: {k: v for k, v in bay.items() if k != "name"} 
                for bay in self.scene.get_bay_data()}
        
        # Update config
        self.config["equipment_positions"] = equipment_positions
        self.config["route_points"] = route_points
        self.config["routes"] = routes
        self.config["bays"] = bays
        
        self.layout_modified = True
        self.status_label.setText("Layout saved to configuration")
    
    def load_layout(self):
        """Load a layout from a file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Layout", "", "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                layout_data = json.load(f)
            
            # Clear the scene
            self.scene.clear()
            self.scene.bay_items = []
            self.scene.route_points = {}
            self.scene.route_paths = []
            self.scene.next_route_point_id = 1
            
            # Update config with layout data
            if "equipment_positions" in layout_data:
                self.config["equipment_positions"] = layout_data["equipment_positions"]
            if "route_points" in layout_data:
                self.config["route_points"] = layout_data["route_points"]
            if "routes" in layout_data:
                self.config["routes"] = layout_data["routes"]
            if "bays" in layout_data:
                self.config["bays"] = layout_data["bays"]
                
            # Reload the layout
            self.load_layout_data()
            self.status_label.setText(f"Layout loaded from {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load layout: {e}")
    
    def toggle_grid(self, checked):
        """Toggle grid visibility."""
        self.scene.show_grid = checked
        self.scene.update()
    
    def fit_view(self):
        """Fit the view to the scene."""
        self.view.fit_scene()
    
    def toggle_route_mode(self, checked):
        """Toggle route creation mode."""
        route_type = self.route_type_combo.currentData()
        self.scene.set_route_mode(checked, route_type)
        # Disable bay mode when route mode is enabled
        if checked and self.bay_action.isChecked():
            self.bay_action.setChecked(False)
        self.status_label.setText(f"Route mode: Click on start item, then end item" if checked else "Ready")
    
    def toggle_bay_mode(self, checked):
        """Toggle bay drawing mode."""
        self.scene.set_bay_mode(checked)
        # Disable route mode when bay mode is enabled
        if checked and self.route_action.isChecked():
            self.route_action.setChecked(False)
        self.status_label.setText("Bay mode: Click and drag to draw bay" if checked else "Ready")
    
    def update_route_type(self, index):
        """Update the route type when combo box changes."""
        if self.route_action.isChecked():
            route_type = self.route_type_combo.currentData()
            self.scene.set_route_mode(True, route_type)
    
    def delete_selected(self):
        """Delete selected items from the scene."""
        self.scene.delete_selected_items()
        self.update_bay_combo()
        self.route_simulator.update_routes_list()
    
    def add_equipment(self):
        """Add new equipment to the scene."""
        eq_type = self.eq_type_combo.currentData()
        bay = self.bay_combo.currentText()
        item_id = self.id_spin.value()
        width = self.width_spin.value()
        height = self.height_spin.value()
        
        # Get bay position from config or bay items
        bay_pos = {"x_offset": 100, "y_offset": 100}  # Default position
        
        # Check if bay exists in the scene
        for bay_item in self.scene.bay_items:
            if bay_item.name == bay:
                bay_pos = {
                    "x_offset": bay_item.pos().x() + bay_item.rect.width()/2,
                    "y_offset": bay_item.pos().y() + bay_item.rect.height()/2
                }
                break
        
        # Fallback to config bays
        if not bay_pos and bay in self.config.get("bays", {}):
            bay_pos = self.config["bays"][bay]
        
        x = bay_pos.get("x_offset", 0)
        y = bay_pos.get("y_offset", 0)
        item = self.scene.add_equipment(eq_type, item_id, bay, x, y, width, height)
        self.scene.clearSelection()
        item.setSelected(True)
        self.status_label.setText(f"Added {eq_type} {item_id} to {bay} with size {width}x{height}")
        self.id_spin.setValue(item_id + 1)
    
    def add_route_point(self):
        """Add a new route point to the scene."""
        # Use the center of the view as the default position
        view_center = self.view.mapToScene(self.view.viewport().rect().center())
        point = self.scene.add_route_point(view_center.x(), view_center.y())
        self.scene.clearSelection()
        point.setSelected(True)
        self.status_label.setText(f"Added Route Point {point.point_id}")
        
        # Update the route simulator
        self.route_simulator.update_routes_list()
    
    def load_background(self):
        """Load a background image for the layout."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp);;DXF Files (*.dxf);;All Files (*)")
        if not file_path:
            return
        _, ext = os.path.splitext(file_path)
        if ext.lower() == ".dxf":
            self.config["cad_file_path"] = file_path
            self.bg_path_label.setText(os.path.basename(file_path))
            img_path = os.path.splitext(file_path)[0] + ".png"
            if os.path.exists(img_path):
                self.scene.set_background_image(img_path)
                self.config["background_image"] = img_path
            else:
                QMessageBox.information(self, "DXF Background", "DXF file selected. In a full implementation, this would be rendered properly.")
        else:
            if self.scene.set_background_image(file_path):
                self.bg_path_label.setText(os.path.basename(file_path))
                self.config["background_image"] = file_path
            else:
                QMessageBox.warning(self, "Error", "Failed to load background image")
    
    def update_bay_combo(self):
        """Update bay combo box with current bay items."""
        current_text = self.bay_combo.currentText()
        self.bay_combo.clear()
        for bay in self.scene.bay_items:
            self.bay_combo.addItem(bay.name)
        
        # Try to restore the previous selection
        index = self.bay_combo.findText(current_text)
        if index >= 0:
            self.bay_combo.setCurrentIndex(index)
    
    def selection_changed(self):
        """Handle scene selection changes."""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.props_label.setText("No item selected")
            self.pos_x_spin.setEnabled(False)
            self.pos_y_spin.setEnabled(False)
            self.props_width_spin.setEnabled(False)
            self.props_height_spin.setEnabled(False)
            self.transit_time_spin.setEnabled(False)
            return
        
        item = selected_items[0]
        
        # Reset all controls first
        self.pos_x_spin.setEnabled(False)
        self.pos_y_spin.setEnabled(False)
        self.props_width_spin.setEnabled(False)
        self.props_height_spin.setEnabled(False)
        self.transit_time_spin.setEnabled(False)
        
        # Based on the item type, update the appropriate controls
        if isinstance(item, EquipmentItem):
            self.update_property_panel(item)
        elif isinstance(item, RoutePointItem):
            self.update_route_point_panel(item)
        elif isinstance(item, RoutePathItem):
            self.update_route_panel(item)
        elif isinstance(item, BayItem):
            self.update_bay_panel(item)
    
    def update_property_panel(self, item=None):
        """Update the property panel with selected equipment item data."""
        if not item:
            selected_items = self.scene.selectedItems()
            if not selected_items or not isinstance(selected_items[0], EquipmentItem):
                return
            item = selected_items[0]
        
        self.props_label.setText(f"Equipment: {item.equipment_type} {item.item_id}\nBay: {item.bay_name}\nSize: {item.width}x{item.height}")
        
        # Block signals during updates
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.props_width_spin.blockSignals(True)
        self.props_height_spin.blockSignals(True)
        
        # Update values
        pos = item.pos()
        self.pos_x_spin.setValue(int(pos.x()))
        self.pos_y_spin.setValue(int(pos.y()))
        self.props_width_spin.setValue(int(item.width))
        self.props_height_spin.setValue(int(item.height))
        
        # Unblock signals
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self.props_width_spin.blockSignals(False)
        self.props_height_spin.blockSignals(False)
        
        # Enable controls
        self.pos_x_spin.setEnabled(True)
        self.pos_y_spin.setEnabled(True)
        self.props_width_spin.setEnabled(True)
        self.props_height_spin.setEnabled(True)
        self.transit_time_spin.setEnabled(False)
    
    def update_route_point_panel(self, item):
        """Update the property panel with selected route point data."""
        self.props_label.setText(f"Route Point: {item.point_id}\nPosition: ({item.pos().x()}, {item.pos().y()})")
        
        # Block signals during updates
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        
        # Update values
        pos = item.pos()
        self.pos_x_spin.setValue(int(pos.x()))
        self.pos_y_spin.setValue(int(pos.y()))
        
        # Unblock signals
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        
        # Enable controls
        self.pos_x_spin.setEnabled(True)
        self.pos_y_spin.setEnabled(True)
        self.props_width_spin.setEnabled(False)
        self.props_height_spin.setEnabled(False)
        self.transit_time_spin.setEnabled(False)
    
    def update_route_panel(self, item):
        """Update the property panel with selected route data."""
        self.props_label.setText(
            f"Route: {item.route_type}\n"
            f"From: {item.get_start_name()}\n"
            f"To: {item.get_end_name()}\n"
            f"Transit Time: {item.transit_time} min"
        )
        
        # Block signals during updates
        self.transit_time_spin.blockSignals(True)
        
        # Update values
        self.transit_time_spin.setValue(item.transit_time)
        
        # Unblock signals
        self.transit_time_spin.blockSignals(False)
        
        # Enable controls
        self.pos_x_spin.setEnabled(False)
        self.pos_y_spin.setEnabled(False)
        self.props_width_spin.setEnabled(False)
        self.props_height_spin.setEnabled(False)
        self.transit_time_spin.setEnabled(True)
    
    def update_bay_panel(self, item):
        """Update the property panel with selected bay data."""
        self.props_label.setText(f"Bay: {item.name}\nSize: {item.rect.width()} x {item.rect.height()}")
        
        # Block signals during updates
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.props_width_spin.blockSignals(True)
        self.props_height_spin.blockSignals(True)
        
        # Update values
        pos = item.pos()
        self.pos_x_spin.setValue(int(pos.x()))
        self.pos_y_spin.setValue(int(pos.y()))
        self.props_width_spin.setValue(int(item.rect.width()))
        self.props_height_spin.setValue(int(item.rect.height()))
        
        # Unblock signals
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self.props_width_spin.blockSignals(False)
        self.props_height_spin.blockSignals(False)
        
        # Enable controls
        self.pos_x_spin.setEnabled(True)
        self.pos_y_spin.setEnabled(True)
        self.props_width_spin.setEnabled(True)
        self.props_height_spin.setEnabled(True)
        self.transit_time_spin.setEnabled(False)
    
    def update_selected_position(self):
        """Update the position of the selected item from spinners."""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        x = self.pos_x_spin.value()
        y = self.pos_y_spin.value()
        
        # Update position
        item.setPos(x, y)
        
        # Update tooltip for route points
        if isinstance(item, RoutePointItem):
            item.setToolTip(f"Route Point {item.point_id}\nPosition: ({x}, {y})")
        
        # Update routes that use this item
        if isinstance(item, (EquipmentItem, RoutePointItem)):
            for route in self.scene.route_paths:
                if route.start_item == item or route.end_item == item:
                    route.update_path()
    
    def update_selected_size(self):
        """Update the size of the selected item."""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        width = self.props_width_spin.value()
        height = self.props_height_spin.value()
        
        # Update equipment item size
        if isinstance(item, EquipmentItem):
            item.width = width
            item.height = height
            item.setToolTip(f"{EQUIPMENT_TYPES[item.equipment_type]['description']}\nID: {item.item_id}\nBay: {item.bay_name}\nSize: {width}x{height}")
            item.update()
        # Update bay size
        elif isinstance(item, BayItem):
            item.rect = QRectF(0, 0, width, height)
            item.update()
        
        # Force scene update
        self.scene.update()
    
    def update_selected_transit_time(self):
        """Update the transit time of the selected route."""
        selected_items = self.scene.selectedItems()
        if not selected_items or not isinstance(selected_items[0], RoutePathItem):
            return
            
        route = selected_items[0]
        transit_time = self.transit_time_spin.value()
        
        # Update transit time
        route.transit_time = transit_time
        
        # Update tooltip
        route.setToolTip(f"{route.route_type} Route\nFrom: {route.get_start_name()}\nTo: {route.get_end_name()}\nTransit Time: {transit_time} min")
    
    def accept(self):
        """Handle dialog acceptance."""
        self.save_layout()
        super().accept()

def show_equipment_layout_editor(sim_service, parent=None):
    """Show the equipment layout editor dialog with the correct config.

    Args:
        sim_service: The SimulationService object containing the configuration.
        parent: The parent widget (optional).

    Returns:
        bool: True if the layout was modified and saved, False otherwise.
    """
    # Pass the configuration dictionary instead of the SimulationService object
    config = sim_service.config  # Assumes sim_service has a 'config' attribute
    editor = EquipmentLayoutEditor(config, parent)
    result = editor.exec_()
    if result == QDialog.Accepted and editor.layout_modified:
        return True
    return False

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    class MockSimulationService:
        def __init__(self):
            self.config = {
                "bays": {
                    "bay1": {"x": 100, "y": 100, "width": 300, "height": 200},
                    "bay2": {"x": 500, "y": 100, "width": 300, "height": 200}
                },
                "units": {
                    "EAF": {"process_time": 50, "capacity": 1, "width": 80, "height": 80},
                    "LMF": {"process_time": 30, "capacity": 2, "width": 70, "height": 70},
                    "Degasser": {"process_time": 40, "capacity": 1, "width": 60, "height": 60},
                    "Caster": {"process_time": 20, "capacity": 1, "width": 100, "height": 50}
                }
            }
    sim_service = MockSimulationService()
    result = show_equipment_layout_editor(sim_service)
    print(f"Editor result: {result}")
    print(f"Updated config: {sim_service.config}")